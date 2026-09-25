#!/usr/bin/env python3
"""The required DCO context has to be reported in a form the ruleset accepts — and never as a false green.

Measured 2026-09-25 on #2209: the head carried a green `DCO / Signed-off-by` **check run** (two of them,
after a `workflow_dispatch` re-report) and the ruleset still answered

    Repository rule violations found
    Required status check "DCO / Signed-off-by" is expected.

with `PUT /pulls/2209/merge` → 405 and `mergeable_state: blocked`. Posting the *same* verdict through the
statuses API (`POST /statuses/{sha}`, context `DCO / Signed-off-by`, state `success`) merged it immediately
(200, squash). Check suites and check runs on that PR and on a PR that had merged minutes earlier were
structurally identical, so the mechanism is not established — what is established is that the context is
satisfied by either form, and that a required context which can go unsatisfied by an invisible evaluation is
exactly the "merge ghost" this repository has been working around (see `docs/agents/repo-operations.md` §4).

So `dco-check.yml` now reports both. The risk that introduces is a **false green**, and the two rules below
are what stop it:

* the status must carry the first step's `passed` *output*, never the step's own outcome — that step
  succeeds even when the verdict is `failure` (a red check run is a report, not an error), so deriving the
  status from `steps.dco.outcome` would turn an unsigned commit into a satisfied required context;
* when there is no verdict at all (the check run could not be created), the step must warn and post nothing.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
WORKFLOW = REPO / ".github" / "workflows" / "dco-check.yml"


def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def steps() -> list[dict]:
    return workflow()["jobs"]["dco"]["steps"]


def step_named(fragment: str) -> dict:
    for step in steps():
        if fragment in (step.get("name") or ""):
            return step
    raise AssertionError(f"no step named like {fragment!r} in {WORKFLOW.name}")


def script_of(step: dict) -> str:
    return str((step.get("with") or {}).get("script") or "")


def test_the_verdict_is_reported_as_a_check_run_and_a_commit_status():
    check_step, status_step = step_named("Check commits"), step_named("commit status")
    assert "checks.create" in script_of(check_step), "the check run is the report a human reads"
    script = script_of(status_step)
    assert "createCommitStatus" in script, (
        "the ruleset has been observed to consider the required context unsatisfied while the check run was "
        "green (#2209, 2026-09-25) — the statuses API is the form that merged it")
    for text in (script_of(check_step), script):
        assert "'DCO / Signed-off-by'" in text, "both reports must use the same context name"


def test_the_status_carries_the_verdict_and_not_the_step_outcome():
    """The one mistake that would forge a required context: a red verdict reported as a green status."""
    script = script_of(step_named("commit status"))
    assert "steps.dco.outcome" not in str(step_named("commit status").get("env") or {}), (
        "the first step succeeds even when DCO fails, so its outcome is not the verdict")
    assert "steps.dco.outputs.passed" in str(step_named("commit status").get("env") or {}), (
        "the status must mirror the `passed` output the check-run step sets")
    assert "setOutput('passed'" in script_of(step_named("Check commits")), (
        "nothing sets `steps.dco.outputs.passed`, so the status step has no verdict to mirror")


def test_the_verdict_is_the_checks_own_pass_value():
    script = script_of(step_named("Check commits"))
    assert "core.setOutput('passed', pass ? 'true' : 'false')" in script, script[-400:]
    assert "state: pass ? 'success' : 'failure'" in script_of(step_named("commit status")), (
        "the status must mirror the verdict in both directions, not only the happy path")


def test_an_absent_verdict_posts_nothing():
    """If the check run could not be created, the first step fails loudly; inventing a pass here would be
    the worst possible outcome for a required context."""
    script = script_of(step_named("commit status"))
    assert "verdict !== 'true' && verdict !== 'false'" in script, script[:400]
    assert "return;" in script, "the absent-verdict path must not fall through to the API call"


def test_the_job_asks_for_the_scope_the_statuses_api_needs():
    permissions = workflow()["permissions"]
    assert permissions.get("statuses") == "write", permissions
    assert permissions.get("checks") == "write", permissions


def test_the_status_step_still_runs_when_the_verdict_is_red():
    """`if: always()` — a step that is skipped on a red verdict would leave exactly the unsigned-commit PR
    without the context its author needs to see."""
    assert str(step_named("commit status").get("if")) == "always()", step_named("commit status").get("if")


def test_the_files_python_is_reading_are_the_real_ones():
    """Guard the guard: a renamed step or job would make every rule above vacuous."""
    data = workflow()
    assert "dco" in data["jobs"], list(data["jobs"])
    assert len(steps()) >= 2, steps()
    with pytest.raises(AssertionError):
        step_named("a step that does not exist")
