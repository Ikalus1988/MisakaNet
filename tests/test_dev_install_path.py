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
    for dependency in ["misakanet-core>=2.7.0", "jsonschema>=4.26.0", "mcp>=2.2.0", "pyyaml>=6.0"]:
        assert dependency in kept, f"{dependency} must survive the filter"
