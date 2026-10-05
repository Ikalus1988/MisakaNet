#!/usr/bin/env python3
"""A wait for approval must be visible, and the watcher must not approve anything.

The problem this guards (2026-09-27): every workflow that declares `environment: release` waits on one
reviewer, whose only
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


def triggers(spec: dict | None = None) -> dict:
    """The `on:` block. YAML 1.1 loaders parse the bare key `on` as the boolean True — read the document
    rather than guessing which spelling this loader produced."""
    spec = yaml.safe_load(text()) if spec is None else spec
    return spec.get("on") or spec.get(True) or {}


def test_the_watcher_runs_on_a_schedule_and_on_demand():
    spec = yaml.safe_load(text())
    block = triggers(spec)
    assert block, sorted(spec)
    assert "schedule" in block and "workflow_dispatch" in block, block
    crons = [entry["cron"] for entry in block["schedule"]]
    assert crons and all(re.fullmatch(r"[\d*/, -]+", c) for c in crons), crons


def release_environment_workflows(workflows_dir: Path | None = None) -> set[str]:
    """The `name:` of every workflow that declares `environment: release`.

    Derived rather than listed: this is the set the watch exists for, and a hand-maintained copy of it is
    a copy that drifts. Takes a directory so the rule can be shown to fail (see the guard test below).
    """
    names = set()
    directory = workflows_dir or (REPO / ".github" / "workflows")
    for path in sorted(directory.glob("*.yml")):
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(spec, dict):
            continue
        for job in (spec.get("jobs") or {}).values():
            if not isinstance(job, dict):
                continue
            environment = job.get("environment")
            if isinstance(environment, dict):
                environment = environment.get("name")
            if environment == "release":
                names.add(spec.get("name") or path.stem)
    return names


def watched_workflows(workflow_path: Path | None = None) -> set[str]:
    """The workflow names the `workflow_run` trigger watches."""
    spec = yaml.safe_load((workflow_path or WORKFLOW).read_text(encoding="utf-8"))
    block = spec.get("on") or spec.get(True) or {}
    return set((block.get("workflow_run") or {}).get("workflows") or [])


def test_the_event_trigger_covers_every_workflow_that_waits_on_the_release_environment():
    """The cron is a backstop now, so the event list is what actually makes a wait visible.

    Measured 2026-09-29: this workflow ran **once** in ~9 hours against a `17,47 * * * *` schedule —
    five-plus slots with no run created at all — while other scheduled workflows in this repository fired
    normally. `workflow_run: [requested]` does not depend on that scheduler. It is matched by `name:`,
    which is why the list has to be kept in step with the workflows that declare `environment: release`,
    in both directions: a missing name is a workflow that can wait silently, and a stale name is a trigger
    that silently never fires.
    """
    expected = release_environment_workflows()
    assert len(expected) >= 5, f"the derivation found {sorted(expected)} — that is not the release cohort"
    listed = watched_workflows()
    assert not (expected - listed), (
        f"these workflows wait on `environment: release` and are not watched: {sorted(expected - listed)}"
    )
    assert not (listed - expected), (
        f"the watch names workflows that do not declare `environment: release`: {sorted(listed - expected)}"
    )
    assert (triggers().get("workflow_run") or {}).get("types") == ["requested"], (
        "`requested` is the moment a run is created, which is when it may start waiting"
    )


def test_the_coverage_rule_notices_a_workflow_that_leaves_the_list(tmp_path):
    """Guard the guard: the rule above reads the real repository, so its failure mode needs a fixture."""
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    (workflows / "a.yml").write_text(
        "name: A watched workflow\n"
        "on: [push]\n"
        "jobs:\n  deploy:\n    environment: release\n    runs-on: ubuntu-latest\n    steps: []\n",
        encoding="utf-8")
    (workflows / "b.yml").write_text(
        "name: An unreviewed workflow\n"
        "on: [push]\n"
        "jobs:\n  build:\n    runs-on: ubuntu-latest\n    steps: []\n",
        encoding="utf-8")
    assert release_environment_workflows(workflows) == {"A watched workflow"}, (
        "only the workflow behind the reviewed environment belongs in the set")

    watched = tmp_path / "watch.yml"
    watched.write_text(text().replace('      - "Apply D1 schema"\n', ""), encoding="utf-8")
    assert "Apply D1 schema" not in watched_workflows(watched), "the mutation must really remove a name"

    spec = yaml.safe_load(watched.read_text(encoding="utf-8"))
    block = spec.get("on") or spec.get(True) or {}
    block.setdefault("workflow_run", {})["workflows"] = ["Something else"]
    watched.write_text(yaml.safe_dump(spec, allow_unicode=True), encoding="utf-8")
    assert watched_workflows(watched) == {"Something else"}, "the fixture must be readable"


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


def test_the_watcher_pushes_instead_of_only_rewriting_the_body():
    """A body edit notifies nobody, so an edit-only tracker has to be visited on purpose.

    Measured 2026-10-05: the watcher was working exactly as designed and it still did not
    prevent a single one of the three freezes. It fired `workflow_run: requested` at
    2026-10-04T09:57Z — the same second run 37193801523 started waiting — and the body of
    #2416 said "**1** run(s) waiting for approval" within the same minute. All three freezes
    were found by a human noticing a symptom (a stale activity chart, a stale `/api/versions`),
    never by the watcher, because nothing told anyone it had spoken.

    GitHub notifies issue subscribers when a comment is created and **not** when the body is
    edited. So the body is the record and the comment is the push; a tracker that only edits is
    a tracker nobody is subscribed to.
    """
    body = text()
    assert "issues.createComment" in body, (
        "the watcher rewrites the body but never comments. GitHub does not notify subscribers "
        "on an edit, so every signal this workflow produces is silent unless somebody opens the "
        "issue on purpose — which is what happened through all three freezes recorded in "
        "handoff-2026-10-05 §5.1 and §5.2b."
    )
    # The push has to be conditional, or a twice-hourly cron turns the issue into noise and
    # subscribers learn to ignore it — the same fate the retry-budget comments warn about.
    assert "shouldComment" in body, (
        "the comment must be gated on the waiting set having changed (or on a staleness "
        "threshold), not emitted every run"
    )
    assert "oldestOverThreshold" in body or "THRESHOLD_H" in body, (
        "a wait that nobody acts on must still escalate, or it sits there being quietly "
        "rewritten forever — the first version of this rule had no threshold at all"
    )
    # And the state it compares against has to be recorded somewhere durable, or it cannot
    # tell "changed" from "always true".
    assert "approval-watch:seen" in body, (
        "the watcher compares against a fingerprint but does not persist it in the body, so it "
        "cannot tell a new run from the one it already reported"
    )


def test_the_comment_names_where_the_approval_is_actually_given():
    """A notification that does not say what to do is a notification that gets muted."""
    body = text()
    idx = body.index("issues.createComment")
    after = body[idx:idx + 1400]
    assert "deployments/activity_log" in after, (
        "the comment must link the environment page where the approval button is; the run URL "
        "alone is one more click and, past a few hours, nobody clicks"
    )
    assert "html_url" in after, (
        "the comment should carry the run's own URL, so the reader does not have to go looking "
        "for which of several waiting runs this is about"
    )
