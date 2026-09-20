#!/usr/bin/env python3
"""A skipped PR gate must be noticed, because nothing else notices it (#1920).

On 2026-09-20 PR #1918 opened and **no `pull_request`-triggered workflow ran at all** — only the
`pull_request_target` ones. `pr-checks.yml` ("Misaka Network Agent Auditor", the job that runs the full test
suite, DCO, the secrets scan and the lesson gate, and publishes the verdict) never started. The two PRs
before it had the same problem, and were merged while I assumed CI was still warming up.

What makes that dangerous rather than annoying is the other half: `main` has **no required status checks**, so
"the gate never ran" and "the gate passed" look the same to a maintainer — a list of green checks, just
shorter. The auditor is the repository's real gate, and it can be absent from a PR without anyone noticing.

`pr-audit-watch.yml` closes that: it looks for PRs whose head commit has no `audit` check-run and starts the
auditor for them. These tests pin the parts that make it a repair rather than a new source of noise.
"""
from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml", reason="PyYAML parses the workflow")

REPO = Path(__file__).resolve().parent.parent
WATCH = REPO / ".github" / "workflows" / "pr-audit-watch.yml"
AUDITOR = REPO / ".github" / "workflows" / "pr-checks.yml"


def _workflow() -> dict:
    return yaml.safe_load(WATCH.read_text(encoding="utf-8"))


def _script() -> str:
    steps = [s for job in _workflow()["jobs"].values() for s in job.get("steps", [])]
    return "\n".join((s.get("run") or "") for s in steps)


def test_the_watcher_repairs_a_missing_audit():
    script = _script()
    assert "gh workflow run pr-checks.yml" in script, (
        "the watcher does not dispatch the auditor, so it only reports the problem")
    assert "-f pr_number=" in script, (
        "the dispatch does not pass the PR number, so the auditor cannot know what to audit")


def test_the_repair_targets_the_branch_being_audited():
    """Dispatching at `main` would audit main and report a green verdict about the wrong code."""
    script = _script()
    assert '--ref "$branch"' in script, (
        "the auditor is dispatched without the PR's own ref, so it would audit whatever the default ref "
        "points at instead of the pull request")


def test_the_watcher_waits_and_caps_itself():
    script = _script()
    assert "MIN_AGE_MINUTES=" in script and "MAX_DISPATCH=" in script, (
        "no grace period or cap: a PR opened seconds ago would be 'repaired' before its normal trigger "
        "fires, and a bad run could dispatch the auditor for every open PR at once")

    # The grace period has to actually be applied, not merely defined.
    assert "-ge \"$MIN_AGE_MINUTES\"" in script, "the grace period is defined but never checked"
    assert "-lt \"$MAX_DISPATCH\"" in script, "the dispatch cap is defined but never checked"


def test_a_fork_pr_gets_a_human_instead_of_a_silent_skip():
    """`workflow_dispatch` cannot target a fork ref, so the watcher must say so out loud."""
    script = _script()
    assert "gh pr comment" in script and "fork" in script, (
        "a fork PR whose audit never ran would be skipped silently - the exact failure this watcher exists "
        "to end")


def test_the_watcher_does_not_run_on_every_push():
    """It is a safety net, not another per-push job adding to the churn it is meant to reduce."""
    triggers = _workflow().get("on") or _workflow().get(True)
    assert "schedule" in triggers, "the watcher must run on a schedule"
    assert "push" not in triggers, (
        "running on push would add a workflow run to every commit, including the ones the auditor already "
        "handled correctly")
