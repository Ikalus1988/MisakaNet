#!/usr/bin/env python3
"""Automation must not pay a model to review its own pull requests.

Measured 2026-10-02: **15 of the last 100 pull requests** were `bot/leaderboard-watch` snapshot chores,
one roughly every 40 minutes. `scripts/ci/land_change.py` enables auto-merge on them, so no human reads
them — but each one still ran three paid model calls: PR-Agent (`Codium-ai/pr-agent`), PR Genius
(`zsxh1990/pr-genius`) and the `audit` job's Agent Quality Score step. That is the bill this file keeps
from coming back, and it is why the check is derived rather than listed: a list would miss the next
workflow someone adds.

Two things have to hold together:

* a workflow that calls a model **and** runs on pull requests must skip the automation's `bot/*` branches;
* the `audit` job must keep running there anyway — it is a required check, and skipping the job to save
  tokens would block every snapshot pull request forever.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO / ".github" / "workflows"

#: Anything that means "this workflow spends money on a model".
MODEL_MARKERS = (
    "Codium-ai/pr-agent",          # the review bot
    "zsxh1990/pr-genius",          # the second review bot
    ".github/actions/score-agent",  # the audit job's quality score
    "OPENAI_KEY",
    "OPENAI_API_BASE",
    "ANTHROPIC",
    "minimax",
)
#: Branches the automation pushes to; `land_change.py` and the release jobs all use this namespace.
AUTOMATION_BRANCH_PREFIX = "bot/"
#: Valid ways to ask for the head branch of a pull request. `github.head_ref` is the shorthand GitHub
#: documents; the payload path works too. `github.event.head_ref` is **not** one of them — the payload has
#: no such key, so that spelling makes the condition false for every pull request, which quietly switches
#: the review off for contributors as well. The first version of this change used it, which is why the
#: invalid form is asserted against below rather than merely not used.
GUARDS = (
    f"!startsWith(github.head_ref, '{AUTOMATION_BRANCH_PREFIX}')",
    f"!startsWith(github.event.pull_request.head.ref, '{AUTOMATION_BRANCH_PREFIX}')",
)
INVALID_GUARD = f"!startsWith(github.event.head_ref, '{AUTOMATION_BRANCH_PREFIX}')"


def _workflows_calling_a_model() -> dict[str, str]:
    found = {}
    for path in sorted(WORKFLOWS.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        if any(marker in text for marker in MODEL_MARKERS):
            found[path.name] = text
    return found


def test_a_model_calling_workflow_that_runs_on_pull_requests_skips_bot_branches():
    offenders = []
    for name, text in _workflows_calling_a_model().items():
        if not re.search(r"^  pull_request(_target)?:", text, re.M):
            continue          # not triggered by pull requests at all
        if not any(guard in text for guard in GUARDS):
            offenders.append(name)
        assert INVALID_GUARD not in text, (
            f"{name} guards on `github.event.head_ref`, which does not exist for a pull request event — "
            "the condition is then false for every pull request, contributors included")
    assert not offenders, (
        "these workflows call a model on every pull request, including the automation's own "
        f"`{AUTOMATION_BRANCH_PREFIX}*` chores that nobody reviews: {offenders}. "
        f"Add `{GUARDS[0]}` to their job/step condition.")


def test_the_required_audit_check_still_runs_on_those_branches():
    """The guard must sit on the *step*, not the job: `audit` is required, so it has to report."""
    text = (WORKFLOWS / "pr-checks.yml").read_text(encoding="utf-8")
    job = text.split("\n  audit:", 1)[1]
    head = job.split("steps:", 1)[0]
    assert not re.search(r"^\s+if:", head, re.M), (
        "the `audit` job now has a condition, so a `bot/*` pull request would never see its required "
        "check report — the model call is what should skip, not the job")
    assert any(guard in job for guard in GUARDS), (
        "the model-scoring step no longer skips the automation's branches")
    assert INVALID_GUARD not in job, "the step guards on a key that the payload does not have"


#: The publishing cadence for the leaderboard snapshot, decided by the maintainer on 2026-10-02: the
#: recompute runs on every push to `main`, but a standings page does not need to be published more than
#: once a day. Change this constant and the one in the workflow together — the failure message says so.
SNAPSHOT_CADENCE_SECONDS = 86400


def test_the_snapshot_lands_at_the_cadence_that_was_decided():
    """The recompute can run on every push; the *pull request* cannot be opened that often."""
    text = (WORKFLOWS / "leaderboard-watch.yml").read_text(encoding="utf-8")
    land = text.split("Land the snapshot", 1)[1]
    assert "RATE_LIMIT_SECONDS=" in land, "the landing step has no rate limit"
    seconds = int(re.search(r"RATE_LIMIT_SECONDS=(\d+)", land).group(1))
    assert seconds == SNAPSHOT_CADENCE_SECONDS, (
        f"the snapshot lands every {seconds}s but the agreed cadence is {SNAPSHOT_CADENCE_SECONDS}s "
        f"({SNAPSHOT_CADENCE_SECONDS // 3600}h). If the cadence really changed, update both this constant "
        "and the workflow.")
    assert "git log -1 --format=%ct -- data/leaderboard.json" in land, (
        "the rate limit must read when the snapshot last landed, from git history rather than a file the "
        "job itself rewrites")
    assert "exit 0" in land.split("RATE_LIMIT_SECONDS=")[1].split("python3 scripts/ci/land_change.py")[0], (
        "exceeding the rate limit has to leave the job green — recomputing and not landing is normal")
