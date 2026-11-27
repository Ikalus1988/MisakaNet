#!/usr/bin/env python3
"""The documented dev install must produce a working install (#1821, the tail).

`pip install -r requirements.txt` is what `docs/agents/repo-operations.md` tells a contributor to run,
and until 2026-09-19 it installed everything *except* the package the repository is: `import
misakanet` worked only because the current directory happened to be on `sys.path`, and the
`misakanet` console script did not exist at all. That is the same "what the user gets is not what the
docs describe" gap #1821 opened about the wheel, one layer down.

The editable line is not free: it runs a PEP 517 build, so a PR that breaks `pyproject.toml` makes it
fail — which is why CI installs the external dependencies first and treats the editable step as
non-fatal. These tests pin both halves: the line exists, and losing it cannot cost a contributor their
entire test run.
"""
from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML parses the workflow")

REPO = Path(__file__).resolve().parent.parent
REQUIREMENTS = REPO / "requirements.txt"
PR_CHECKS = REPO / ".github" / "workflows" / "pr-checks.yml"

EDITABLE = "-e ."


def _pip_requirements() -> list[str]:
    """Non-comment, non-empty lines of requirements.txt."""
    return [line.strip() for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")]


def _install_step() -> str:
    workflow = yaml.safe_load(PR_CHECKS.read_text(encoding="utf-8"))
    for job in workflow["jobs"].values():
        for step in workflow.get("steps", []) or job.get("steps", []):
            if (step.get("name") or "") == "Install Dependencies":
                return step["run"]
    raise AssertionError("the Install Dependencies step disappeared from pr-checks.yml")


def test_the_documented_dev_install_installs_this_package():
    assert EDITABLE in _pip_requirements(), (
        "requirements.txt must install the repository's own package in editable mode, or the "
        "documented `pip install -r requirements.txt` leaves `import misakanet` and the `misakanet` "
        "command dependent on the current directory"
    )


def test_the_editable_install_cannot_cost_a_contributor_the_test_suite():
    """The reason the repository dropped `-e .` once — it must not come back."""
    script = _install_step()
    code = "\n".join(line for line in script.splitlines() if not line.strip().startswith("#"))
    # The external dependencies are installed from a copy with the editable line removed, so a
    # broken PEP 517 build cannot take them down with it.
    assert "grep -v" in code and "/tmp/requirements-external.txt" in code, (
        "install the external dependencies from a requirements copy that excludes `-e .`"
    )
    assert "pip install --no-deps -e ." in code, "the editable install must be its own, separate step"
    assert "::warning::" in code, (
        "a failed editable install must be reported as a warning a maintainer can act on"
    )
    # The hard failure stays on the external dependencies — that is a real install failure.
    assert "Core dependency install failed" in code
    # And the suite keeps working against the checkout in either case.
    assert "PYTHONPATH=$(pwd)" in code


def test_the_fallback_is_what_actually_gets_installed():
    """Execute the split the workflow does, on this repository's own file.

    Pins the mechanism rather than the text: the filtered copy must keep every real dependency and
    drop exactly the editable line.
    """
    import subprocess

    filtered = subprocess.run(
        ["grep", "-v", r"^[[:space:]]*-e[[:space:]]*\.", str(REQUIREMENTS)],
        capture_output=True, text=True, check=True).stdout
    kept = [line.strip() for line in filtered.splitlines()
            if line.strip() and not line.strip().startswith("#")]
    dropped = [line for line in _pip_requirements() if line not in kept]
    assert dropped == [EDITABLE], f"the filter must drop exactly the editable line, dropped: {dropped}"
    # And nothing else may be dropped, for *any* dependency — which is what this test used to
    # assert badly. It ended with a loop over four hand-picked version strings, one of them
    # "mcp>=2.2.0", which is the text this test's own docstring says it does not pin. Dependabot
    # #3160 raised mcp to >=2.3.0, changed nothing else, and turned it red on all seven platforms.
    # Those four literals were also strictly weaker than the line above, which is derived: it
    # covers every dependency rather than four of them. Asserting the exact filtered contents
    # pins the mechanism, keeps a version bump out of its blast radius, and would still fail if
    # the filter quietly dropped a dependency nobody thought to write down.
    assert kept == [line for line in _pip_requirements() if line != EDITABLE], (
        "the filtered copy must be requirements.txt minus exactly the editable line, in order; "
        f"got {kept}"
    )


def test_the_wheel_and_the_dev_install_need_the_same_dependencies():
    """One dependency set, not two that drifted (#5863's review, measured 2026-11-27).

    `requirements.txt` is what every workflow, `AGENTS.md`, `docs/agents/repo-operations.md` and the
    install smoke test actually install. `pyproject.toml`'s `dependencies` is what `pip install
    misakanet` and `uv sync` install. They are two spellings of one list, and nothing compared them.

    What that cost, on 3.23.0: the wheel declared `misakanet-core` alone, so `pip install misakanet`
    produced an environment without `jsonschema`, `mcp` or `pyyaml`. `python -m misakanet` reaches
    none of them, so `pypi-wheel-smoke.yml` stayed green while five `scripts/` modules raised
    `ModuleNotFoundError`. Worse, `uv sync` resolves from *this* list, so `uv.lock` had never
    contained `jsonschema` or `mcp` at all — 110 locked packages, neither of them — and a
    contributor following the "single source of truth" file got an environment that cannot run the
    test suite's dependency-sensitive half.

    This asserts set equality of the non-editable, non-extra requirements, so a package added to
    either file alone is red until it reaches the other. It deliberately does **not** compare
    versions: `requirements.txt` and the wheel may reasonably carry different floors for the same
    name only if someone decides that on purpose, and a name-only comparison is the half that
    silently broke.
    """
    import tomllib  # stdlib on the 3.11 floor

    project = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))["project"]

    def names(distributions) -> set[str]:
        # A version specifier starts at the first character that cannot appear in a distribution
        # name. `re.split` on a character class is the obvious way and the one that broke here:
        # the class needs `[` and `(` escaped inside it, and those escapes do not survive a
        # round-trip through some editors. This loop has no escapes to lose.
        out: set[str] = set()
        for spec in distributions:
            text = str(spec).strip()
            if not text:
                continue
            cut = len(text)
            for index, char in enumerate(text):
                if char in "<>=!~[(":
                    cut = index
                    break
            out.add(text[:cut].strip().lower().replace("_", "-"))
        return out

    wheel = names(project.get("dependencies") or [])
    dev = names(line for line in _pip_requirements() if line != EDITABLE)

    assert wheel == dev, (
        "pyproject.toml's `dependencies` and requirements.txt disagree — one of them installs "
        "something the other does not, so `pip install misakanet` or `uv sync` produces an "
        "environment the documented dev install would not, or the reverse.\n"
        f"  only in pyproject.toml: {sorted(wheel - dev)}\n"
        f"  only in requirements.txt: {sorted(dev - wheel)}"
    )
