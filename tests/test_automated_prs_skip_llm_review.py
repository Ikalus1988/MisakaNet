#!/usr/bin/env python3
"""Automation must not pay a model to review its own pull requests.

Measured 2026-10-02: **15 of the last 100 pull requests** were `bot/leaderboard-watch` snapshot chores —
median gap **84 minutes** over that window (mean 121), roughly one every hour and a half. They are merged
by `scripts/ci/land_change.py` through GitHub's native auto-merge, so nobody reads them, but each one still
triggers **PR-Agent** (`Codium-ai/pr-agent`), the one paid model call in the set. Measured, not assumed:

* `./.github/actions/score-agent` is 118 lines of `gh api`, `grep`, `bc` and `date` — **no model, no API
  key** (0 matches for any provider marker);
* `zsxh1990/pr-genius` is a composite that runs `python3 -m prgenius analyze <title> --repo <repo>
  --body <body>`; this repository hands it **no model credential**, only the token it labels with, so from
  here it is not provably a model call.

So the honest saving is **one paid review per chore pull request** (about 15 % of pull requests stop paying
for PR-Agent), not three. The first version of this file said three, counting the two free analyses; the
review that caught it also found the ruleset requires **four** status checks on `main`, not three.

Two things have to hold together:

* a workflow that calls a model **and** runs on pull requests must skip the automation's `bot/*` branches —
  the check is derived from each workflow's own `jobs:` (parsed as YAML), so a second model job added to a
  file that already has one, a `.yaml` extension, or a marker added later is covered rather than missed;
* the `audit` job must keep running there anyway — it is a required check, and skipping the job to save
  work would block every snapshot pull request forever.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
WORKFLOWS = REPO / ".github" / "workflows"

#: Anything that means "this job spends money on a model". `/cf/` and `AI_GATEWAY` cover the Workers AI
#: job (`benchmark-workers-ai.yml`, `@cf/meta/llama-…` through `AI_GATEWAY_TOKEN`), which a hand-written
#: list of agent actions had missed — the review demonstrated it by adding a `pull_request:` trigger to
#: that file and watching this rule stay green.
MODEL_MARKERS = (
    "Codium-ai/pr-agent",
    "zsxh1990/pr-genius",
    ".github/actions/score-agent",
    "OPENAI_KEY",
    "OPENAI_API_BASE",
    "ANTHROPIC",
    "minimax",
    "@cf/",
    "AI_GATEWAY",
    "workers-ai",
)
#: Branches the automation pushes to; `land_change.py` and the release jobs all use this namespace.
AUTOMATION_BRANCH_PREFIX = "bot/"
#: Valid ways to name the **head branch** of a pull request. `github.head_ref` is the shorthand GitHub
#: documents; the payload path says the same thing. Two spellings that do *not* work, both rejected below
#: rather than merely avoided:
#:
#: * `github.event.head_ref` — the payload has no such key, and GitHub documents that dereferencing a
#:   nonexistent property "will evaluate to an empty string", so `!startsWith('', 'bot/')` is **true for
#:   every pull request**: the guard skips nothing at all. (The first version of this change used it and
#:   described the consequence backwards — as if the review had switched off for contributors.)
#: * `github.ref_name` — documented as the *merge* ref for a pull request (`<pr_number>/merge`), not the
#:   source branch, so it matches `bot/` for nothing either.
GUARDS = (
    f"!startsWith(github.head_ref, '{AUTOMATION_BRANCH_PREFIX}')",
    f"!startsWith(github.event.pull_request.head.ref, '{AUTOMATION_BRANCH_PREFIX}')",
)
INVALID_GUARDS = (
    f"!startsWith(github.event.head_ref, '{AUTOMATION_BRANCH_PREFIX}')",
    f"!startsWith(github.ref_name, '{AUTOMATION_BRANCH_PREFIX}')",
)
#: The publishing cadence for the leaderboard snapshot, decided by the maintainer on 2026-10-02: the
#: recompute runs on every push to `main`, but a standings page does not need to be published more than
#: once a day. Measured the same day, before the decision: 0 of the last 42 gaps between snapshots were
#: 24 h or longer, so this bound binds on nearly every push. Change this constant and the workflow
#: together — the failure message says so.
SNAPSHOT_CADENCE_SECONDS = 86400


def _workflow_files() -> list[Path]:
    """`.yml` **and** `.yaml` — the first version of this rule globbed only `*.yml`."""
    return sorted(set(WORKFLOWS.glob("*.yml")) | set(WORKFLOWS.glob("*.yaml")))


def _jobs(path: Path) -> dict[str, dict]:
    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    jobs = document.get("jobs")
    return jobs if isinstance(jobs, dict) else {}


def _runs_on_pull_requests(path: Path) -> bool:
    """True when the workflow's `on:` includes a pull request trigger."""
    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    trigger = document.get("on") or document.get(True)   # YAML 1.1 parses bare `on:` as boolean True
    if isinstance(trigger, str):
        return trigger.startswith("pull_request")
    if isinstance(trigger, list):
        return any(str(item).startswith("pull_request") for item in trigger)
    if isinstance(trigger, dict):
        return any(str(key).startswith("pull_request") for key in trigger)
    return False


def _guarded(job: dict) -> bool:
    """The guard must sit on the job itself or on **the step that calls the model**.

    Not the union of every condition in the job: the review moved the guard from `pr-agent-review.yml`'s
    job `if:` onto a decoy step (`if: <guard>` + `run: echo`) and the first version of this rule stayed
    green while the model job ran unguarded on every `bot/*` pull request.
    """
    if any(guard in str(job.get("if", "")) for guard in GUARDS):
        return True
    for step in job.get("steps") or []:
        if not isinstance(step, dict):
            continue
        blob = json.dumps(step)
        if not any(marker in blob for marker in MODEL_MARKERS):
            continue
        if any(guard in str(step.get("if", "")) for guard in GUARDS):
            return True
    return False


def test_a_job_calling_a_model_skips_the_automation_branches():
    """Per **job**, not per file: a second model job in an already-guarded file must carry its own guard.

    The review broke the first version exactly there — it appended an unguarded `Codium-ai/pr-agent` job to
    `pr-agent-review.yml` and the rule stayed green, because it only asked whether the guard appeared
    anywhere in the file.
    """
    offenders = []
    for path in _workflow_files():
        if not _runs_on_pull_requests(path):
            continue
        for name, job in _jobs(path).items():
            blob = json.dumps(job)
            if not any(marker in blob for marker in MODEL_MARKERS):
                continue
            if not _guarded(job):
                offenders.append(f"{path.name}:{name}")
    assert not offenders, (
        "these jobs call a model on every pull request, including the automation's own "
        f"`{AUTOMATION_BRANCH_PREFIX}*` chores that nobody reviews: {offenders}. "
        f"Add `{GUARDS[0]}` to the job or to the step that calls the model.")


def test_no_guard_uses_a_spelling_that_cannot_match_a_head_branch():
    for path in _workflow_files():
        text = path.read_text(encoding="utf-8")
        for invalid in INVALID_GUARDS:
            assert invalid not in text, (
                f"{path.name} guards on `{invalid.split('(')[1].split(',')[0]}`, which cannot match a "
                "`bot/*` head branch: `github.event.head_ref` does not exist (empty string, so the "
                "condition is true everywhere) and `github.ref_name` is the merge ref `<n>/merge` for a "
                "pull request. Both make the guard a no-op.")


def test_the_required_audit_check_still_runs_on_those_branches():
    """The guard must sit on the *step*, not the job: `audit` is required, so it has to report.

    The ruleset on `main` (23826057, no bypass actors) requires **four** contexts — `DCO / Signed-off-by`,
    `test (ubuntu-latest, 3.11)`, `gate` and `audit` — so a skipped `audit` job would leave every snapshot
    pull request waiting forever on a check that never reports.
    """
    text = (WORKFLOWS / "pr-checks.yml").read_text(encoding="utf-8")
    job = _jobs(WORKFLOWS / "pr-checks.yml")["audit"]
    assert not job.get("if"), (
        "the `audit` job now has a condition, so a `bot/*` pull request would never see its required "
        "check report — the extra work is what should skip, not the job")
    assert _guarded(job), "the model-scoring step no longer skips the automation's branches"


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
