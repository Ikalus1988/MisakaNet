#!/usr/bin/env python3
"""`uv.lock` matches `pyproject.toml` — with the project's own version deliberately exempt.

Measured 2026-10-06, and the exemption is the whole point of this file
--------------------------------------------------------------------------
The obvious gate is `uv lock --check` in CI. Measured on the last 28 release commits:

    0be30b18  pyproject=2.41.3  uv.lock=2.39.0  uv.lock touched=0  chore(main): release 2.41.3
    babb2a9e  pyproject=2.41.2  uv.lock=2.39.0  uv.lock touched=0  chore(main): release 2.41.2
    … 28 for 28, `uv.lock touched=0` every time

release-please bumps `[project].version` in `pyproject.toml` and cannot re-lock (it has no `uv`).
So a naive `uv lock --check` is **red within minutes of every release** and stays red until some
unrelated dependabot PR happens to re-lock. That is a gate that is wrong for a reason nobody can
act on — the exact failure mode this repository has already been bitten by (see the DCO/pull-request
comment in `pr-checks.yml` about red legs nobody can act on training everyone to ignore red).

`uv.lock` does record the project's version (`[[package]] name = "misakanet" / version = "2.41.3"`).
Right now it matches, but only because `a4ff516d` (dependabot, #2890) re-locked after 2.41.3 and
picked up the new number by luck. Nothing maintains it.

So this gate neutralises the version before checking: it copies `pyproject.toml` + `uv.lock` to a
temp directory, rewrites pyproject's version to whatever the lock already records, and checks
that project. What remains is the thing release-please never touches and humans/dependabot always
get wrong — the dependency set. That is the drift that has actually bitten this repository before
(`docs/maintainer/pr-genius-observation.md`: "#2121 high_risk | CI failure (uv.lock drift), needed
lockfile update").

The version drift is not fixed here; it is reported, because the fix belongs in the release plumbing
(re-lock after release-please), not in a test.

What this checks
----------------
1. **The gate is green on a clean checkout** — the version-neutralised `uv lock --check` passes.
2. **The gate is not vacuous** — the same command, on the same temp copy, with the dependency floor
   raised in `pyproject.toml` only, must fail. Without this, check 1 would pass just as happily
   against a `uv.lock` that had been emptied of the project's dependencies (verified: removing
   `misakanet-core` from the lock's root package leaves `uv lock --check` at exit 0, because the
   *resolved package set* is unchanged — so that mutation would have looked like a passing gate).
3. **The lock still names this project**, so check 1 cannot pass against a lockfile that no longer
   describes the project at all.

`uv` is installed in CI (`astral-sh/setup-uv`, pinned by SHA, outside the `scope == 'full'`
condition) precisely so this does not skip there. Locally, a missing `uv` skips with a loud reason
rather than blocking a contributor — and `test_ci_installs_uv` below fails if that setup step is
ever removed, so the skip cannot become permanent.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest
import tomllib

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
UV_LOCK = REPO_ROOT / "uv.lock"
PR_CHECKS = REPO_ROOT / ".github" / "workflows" / "pr-checks.yml"

LOCK_ROOT_RE = re.compile(r'\[\[package\]\]\nname = "misakanet"\nversion = "([^"]+)"')
PYPROJECT_VERSION_RE = re.compile(r'^version = "[^"]*"', re.MULTILINE)
UV = shutil.which("uv")


def _requires_uv() -> None:
    if UV is None:
        pytest.skip("uv is not installed — CI installs it via astral-sh/setup-uv; see "
                    "test_ci_installs_uv, which fails if that step is removed")


def _stage(tmp_path: Path) -> Path:
    """A temp project whose pyproject version matches what the lock already records."""
    staged = tmp_path / "project"
    staged.mkdir()
    shutil.copy(PYPROJECT, staged / "pyproject.toml")
    shutil.copy(UV_LOCK, staged / "uv.lock")

    match = LOCK_ROOT_RE.search((staged / "uv.lock").read_text(encoding="utf-8"))
    assert match, "uv.lock no longer has a [[package]] entry named 'misakanet'"
    text = (staged / "pyproject.toml").read_text(encoding="utf-8")
    (staged / "pyproject.toml").write_text(
        PYPROJECT_VERSION_RE.sub(f'version = "{match.group(1)}"', text, count=1),
        encoding="utf-8",
    )
    return staged


def _lock_check(staged: Path, timeout: float = 300.0) -> subprocess.CompletedProcess:
    return subprocess.run(
        [UV, "lock", "--check"], cwd=staged, capture_output=True, text=True, timeout=timeout,
    )


# ── the gate itself ──────────────────────────────────────────────────────────────────────────────

def test_uv_lock_check_passes_with_the_release_version_exempted(tmp_path):
    """The green half. If this fails, a dependency changed without `uv lock` being re-run."""
    _requires_uv()
    result = _lock_check(_stage(tmp_path))
    assert result.returncode == 0, (
        "uv.lock is out of sync with pyproject.toml — run `uv lock` and commit the result.\n"
        f"stdout: {result.stdout.strip()}\nstderr: {result.stderr.strip()}"
    )


def test_uv_lock_check_detects_dependency_drift(tmp_path):
    """The not-vacuous half, run on the staged copy above.

    Raising the floor to a version that does not exist leaves the lock's resolved package set
    unusable, which is exactly what a human editing `pyproject.toml` without re-locking does. It
    fails during resolution, so it needs no network and stays deterministic.
    """
    _requires_uv()
    staged = _stage(tmp_path)
    pyproject = staged / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    drifted = text.replace('"misakanet-core>=2.7.0"', '"misakanet-core>=99.0.0"')
    assert drifted != text, (
        "pyproject.toml no longer declares `misakanet-core>=2.7.0`; this test's drift fixture has "
        "to track the real dependency or it proves nothing"
    )
    pyproject.write_text(drifted, encoding="utf-8")

    result = _lock_check(staged)
    assert result.returncode != 0, (
        "`uv lock --check` accepted a pyproject.toml whose dependency floor the lock "
        "cannot satisfy — the gate cannot see drift and is not worth running"
    )


def test_uv_lock_still_describes_this_project():
    """Guards the regex both other tests depend on."""
    lock = tomllib.loads(UV_LOCK.read_text(encoding="utf-8"))
    root = next((p for p in lock.get("package", []) if p.get("name") == "misakanet"), None)
    assert root is not None, "uv.lock has no package entry named 'misakanet'"
    assert root.get("source", {}).get("editable") == ".", (
        f"uv.lock's misakanet entry is {root.get('source')!r}, not the editable root — this lock "
        f"was generated for a different layout and `uv lock --check` would not be checking us"
    )
    names = {d.get("name") for d in root.get("dependencies", [])}
    assert "misakanet-core" in names, (
        f"uv.lock's misakanet entry no longer depends on misakanet-core: {names}"
    )


# ── keeping the gate from silently turning into a skip ──────────────────────────────────────────

def test_ci_installs_uv_outside_the_scope_condition():
    """A runner with no `uv` skips every test here; a permanent skip is a gate in name only."""
    workflow = PR_CHECKS.read_text(encoding="utf-8")
    assert "astral-sh/setup-uv" in workflow, (
        "pr-checks.yml no longer installs uv, so every test in this file skips on CI and the "
        "uv.lock drift they police becomes invisible again"
    )
    install_step = re.search(r"astral-sh/setup-uv@[0-9a-f]{40}", workflow)
    assert install_step, "setup-uv must be pinned by SHA like every other action in this workflow"

    # …and it must not sit behind the scope condition, or lessons-only pull requests skip the gate.
    lines = workflow.splitlines()
    step_line = next(i for i, ln in enumerate(lines) if "astral-sh/setup-uv" in ln)
    scope_line = next(
        (i for i, ln in enumerate(lines) if "steps.scope.outputs.scope ==" in ln), None
    )
    assert scope_line is not None and step_line < scope_line, (
        f"setup-uv (line {step_line + 1}) must be declared before the first scope condition "
        f"(line {scope_line + 1}), or it is skipped on non-full pull requests"
    )
