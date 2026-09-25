#!/usr/bin/env python3
"""Landing must push *the generated files*, not whichever branch the checkout happens to be on.

Measured 2026-09-25. `release-please.yml` runs, in order: the release-please action (which leaves the
workspace on `release-please--branches--main`), the changelog repair (which committed there), then the step
that lands the version sync. `land_change.py` commits on **HEAD** and pushes `HEAD:refs/heads/<branch>`, so
all three commits went to `bot/release-version-sync`:

```
458011c6a  chore(main): release 2.35.0                                  ← release-please
94644c7d0  chore(changelog): drop the duplicate entries …                ← the repair step
841e428c6  docs: sync version to v2.34.0                                ← the lander (PR head)
```

The pull request was titled "docs: sync version to v2.34.0" and carried eleven files, including
`.release-please-manifest.json`, `pyproject.toml`, `workers/register-proxy-sw.js` and `server.json` — the
entire **2.35.0 version bump**. Merging it would have moved the version on `main` without the release flow's
tag and dispatches; `pr-shape-guard` flagged it, which is how it was found.

The guard is the loud version of the rule: refuse to land when `HEAD` is not `origin/<base>`, and say what
moved the checkout. The workflow-side fix (a worktree for the repair, `git checkout --force main` after the
release-please action) is pinned in `tests/test_dedupe_release_entries.py`.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import scripts.ci.land_change as land_change  # noqa: E402

pytestmark = pytest.mark.skipif(
    not shutil.which("git"), reason="these rules drive git; without it they prove nothing"
)


def _git(cwd: Path, *args: str) -> str:
    env = dict(os.environ)
    env.update({"GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.com",
                "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.com",
                "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"})
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=env,
                          check=True).stdout.strip()


def scratch_checkout(tmp_path: Path, *, on_other_branch: bool) -> Path:
    """A repository with `main`, a branch whose commit `main` does not have, and an `origin/main` ref.

    `on_other_branch` reproduces the state the release workflow leaves behind: HEAD on a branch that is
    ahead of the branch the pull request targets.
    """
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True,
                   capture_output=True, env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull})
    work = tmp_path / "work"
    subprocess.run(["git", "clone", "-q", str(origin), str(work)], check=True, capture_output=True,
                   env={**os.environ, "GIT_CONFIG_GLOBAL": os.devnull})
    _git(work, "config", "user.email", "t@example.com")
    _git(work, "config", "user.name", "T")
    (work / "f.txt").write_text("one\n", encoding="utf-8")
    _git(work, "add", "f.txt")
    _git(work, "commit", "-q", "-m", "base")
    _git(work, "branch", "-M", "main")
    _git(work, "push", "-q", "origin", "main")
    if on_other_branch:
        _git(work, "checkout", "-q", "-b", "release-branch")
        (work / "bump.txt").write_text("2.35.0\n", encoding="utf-8")
        _git(work, "add", "bump.txt")
        _git(work, "commit", "-q", "-m", "chore(main): release 2.35.0")
    return work


# ── the predicate ───────────────────────────────────────────────────────────────────
def test_head_is_the_base_branch_on_a_fresh_checkout(tmp_path):
    work = scratch_checkout(tmp_path, on_other_branch=False)
    same, head, base = land_change.Land("owner/repo", "stub", cwd=work).head_is("main")
    assert same is True and head and base and head == base


def test_head_is_not_the_base_branch_when_a_step_moved_the_checkout(tmp_path):
    work = scratch_checkout(tmp_path, on_other_branch=True)
    same, head, base = land_change.Land("owner/repo", "stub", cwd=work).head_is("main")
    assert same is False, (head, base)
    assert head != base and base, "the base ref must be readable for the message to be useful"


def test_a_missing_base_ref_is_not_treated_as_a_mismatch(tmp_path):
    """A shallow or single-branch checkout has no `origin/main`; that is not this rule's business."""
    work = scratch_checkout(tmp_path, on_other_branch=False)
    same, head, base = land_change.Land("owner/repo", "stub", cwd=work).head_is("no-such-base")
    assert same is True and base == ""


# ── the wiring: the refusal happens before anything is staged ───────────────────────
def _args(tmp_path: Path) -> list[str]:
    return ["--branch", "bot/x", "--title", "docs: sync version", "--paths", "f.txt",
            "--repo", "Ikalus1988/MisakaNet", "--dry-run"]


def test_landing_refuses_when_the_checkout_was_moved(tmp_path, monkeypatch, capsys):
    work = scratch_checkout(tmp_path, on_other_branch=True)
    monkeypatch.setattr(land_change, "REPO_ROOT", work)
    monkeypatch.setenv("GH_TOKEN", "stub")

    rc = land_change.main(_args(tmp_path))
    err = capsys.readouterr()

    assert rc == 1, "landing from a moved checkout must fail, not open a misleading pull request"
    assert "the workflow moved the checkout" in (err.out + err.err)
    assert "git checkout --force main" in (err.out + err.err), "the message must say how to fix the workflow"


def test_landing_proceeds_on_the_base_branch(tmp_path, monkeypatch, capsys):
    work = scratch_checkout(tmp_path, on_other_branch=False)
    monkeypatch.setattr(land_change, "REPO_ROOT", work)
    monkeypatch.setenv("GH_TOKEN", "stub")

    rc = land_change.main(_args(tmp_path))
    out = capsys.readouterr().out

    assert rc == 0, out
    assert '"dry_run": true' in out, out
