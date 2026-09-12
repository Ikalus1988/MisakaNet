#!/usr/bin/env python3
"""Every workflow that shells out to `gh` must authenticate it (2026-09-12).

Why this exists
---------------
`Intake Salvage Digest` failed on its daily schedule from at least 2026-09-09 with
nothing but `Process completed with exit code 4`. Two details made it invisible:

* the job declared `permissions: issues: write` but never exported `GH_TOKEN`, so
  `gh` was unauthenticated — exit code 4 is gh's auth failure, not a shell error;
* the step runs under `bash -e`, and its first `gh` call ended with `2>/dev/null`,
  so the message that would have named the problem was discarded.

The consequence was silent and load-bearing: the digest that exists to surface
auto-rejected intakes never ran, so the salvage queue sat untouched while every
run reported a green schedule (a failed run is easy to miss in a list of daily
schedules).

A test cannot call `gh` with the runner's token, but it can check the invariant
that decides whether the call can work at all: `gh` needs GH_TOKEN (or
GITHUB_TOKEN) in its environment, and declaring workflow `permissions` does not
put it there.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO / ".github" / "workflows"

# `gh ` at the start of a command (allowing `$(gh ...)`, `| gh ...`, `&& gh ...`),
# but not the word inside prose or a URL.
GH_CALL = re.compile(r"(?:^|[|&(]\s*|\$\(\s*)gh\s+\w", re.MULTILINE)


def _workflow_files() -> list[Path]:
    return sorted(p for p in WORKFLOWS.glob("*.y*ml"))


def _gh_steps(workflow: dict):
    """Yield (job_name, step, job_env) for every step whose `run:` calls gh."""
    for job_name, job in (workflow.get("jobs") or {}).items():
        job_env = job.get("env") or {}
        for step in job.get("steps") or []:
            run = step.get("run") or ""
            if GH_CALL.search(run):
                yield job_name, step, job_env


def test_gh_is_authenticated_wherever_a_workflow_uses_it():
    offenders = []
    checked = 0
    for path in _workflow_files():
        workflow = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for job_name, step, job_env in _gh_steps(workflow):
            checked += 1
            step_env = step.get("env") or {}
            has_token = any(
                key in merged
                for merged in (step_env, job_env)
                for key in ("GH_TOKEN", "GITHUB_TOKEN")
            ) or "token" in (step.get("with") or {})   # checkout-style token input
            if not has_token:
                offenders.append(f"{path.name}:{job_name}:{step.get('name', '(unnamed step)')}")
    assert checked, "no workflow step calls gh — this guard has gone stale, check GH_CALL"
    assert offenders == [], (
        "these steps call gh without GH_TOKEN/GITHUB_TOKEN in scope, so gh runs "
        "unauthenticated and exits 4 (and `permissions:` does not export it):\n  - "
        + "\n  - ".join(offenders)
    )


def test_the_salvage_digest_does_not_swallow_gh_errors():
    """The failure that motivated this file was silenced by `2>/dev/null`.

    Suppressing stderr on a `gh` call is what turned a one-line auth error into a
    multi-day mystery, so keep it off the inventory call in particular.
    """
    text = (WORKFLOWS / "intake-salvage-digest.yml").read_text(encoding="utf-8")
    assert "gh issue list" in text
    for line in text.splitlines():
        if "gh " in line and "2>/dev/null" in line:
            pytest.fail(f"a gh call discards its error output, hiding the reason: {line.strip()}")
    # The digest step must fail loudly instead: `bash -e` is in effect, so a bare
    # failure with stderr dropped is exactly the reported symptom.
    assert "GH_TOKEN" in text, "the digest job must export a token for gh"
