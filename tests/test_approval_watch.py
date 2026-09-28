#!/usr/bin/env python3
"""A wait for approval must be visible, and the watcher must not approve anything.

The problem this guards (2026-09-27): eight workflows sit behind the `release` environment, whose only
required reviewer is the owner, and **nothing notifies anyone** when one of them starts waiting. Measured:
three runs waited on one person in a day (worker deploy + two npm publishes), one for ~23 hours; the health
snapshot had recorded a run waiting since 2026-09-21T12:13Z with no notification anywhere.

The tempting fix — move the deploy credential out of the reviewed environment — is refused by
`tests/test_secret_scoping.py`, and rightly: the workflow file is editable by anyone who can merge, so the
environment reviewer is what stops a merged edit from reaching production. Hence the watcher below: it
changes no credential scoping, it only reports.

Both halves are asserted here, because the second is a safety property that is easy to lose by accident:
a watcher that *approves* would silently remove the review it exists to report on.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
WORKFLOW = REPO / ".github" / "workflows" / "approval-watch.yml"


def text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_the_watcher_runs_on_a_schedule_and_on_demand():
    spec = yaml.safe_load(text())
    # `on` is parsed as the boolean True by YAML 1.1 loaders — read the document rather than guessing.
    triggers = spec.get("on") or spec.get(True)
    assert triggers, sorted(spec)
    assert "schedule" in triggers and "workflow_dispatch" in triggers, triggers
    crons = [entry["cron"] for entry in triggers["schedule"]]
    assert crons and all(re.fullmatch(r"[\d*/, -]+", c) for c in crons), crons


def test_it_asks_for_runs_that_are_waiting_for_approval():
    body = text()
    assert "status: 'waiting'" in body, "the watcher no longer filters on the waiting status"
    assert "listWorkflowRunsForRepo" in body, "the watcher does not list runs"


def test_it_reports_into_one_tracking_issue_instead_of_creating_a_new_one_each_time():
    body = text()
    assert "approval-watch" in body, "no tracking label"
    assert "issues.update" in body and "issues.create" in body, (
        "the watcher must update its issue and create it only when missing, or the daily noise is worse "
        "than the wait it reports"
    )
    assert "deployments/activity_log" in body, "the report must link where the approval is actually given"


def test_the_watcher_never_approves_a_deployment():
    """The safety property: this is an observer. Approving is the human's decision, and automating it would
    defeat the environment reviewer that the whole design rests on."""
    body = text()
    for forbidden in ("/approve", "review_pending", "pending_deployments", "approveWorkflowRun"):
        assert forbidden not in body, (
            f"the watcher contains {forbidden!r} — an automation that approves deployments removes the "
            "review it exists to report on"
        )
    perms = yaml.safe_load(text())["jobs"]["report"]["steps"][0].get("with", {})
    assert perms, perms


def test_the_permissions_are_read_only_where_they_can_be():
    spec = yaml.safe_load(text())
    perms = spec["permissions"]
    assert perms["contents"] == "read", perms
    assert perms["actions"] == "read", perms
    assert perms["issues"] == "write", perms
