#!/usr/bin/env python3
"""The 21-minute job must not keep burning after a newer push replaces it.

Measured 2026-11-27, over the last 100 runs of `pr-checks.yml`:

* **18 runs were started and then superseded** by a later run on the same pull request;
* the discarded remainder alone burned **1,749 runner-minutes — 29 hours**;
* one force-push to `intake-batch/2026-11-25` accounted for **1,302** of those.

`ci-cross-platform.yml` has carried `cancel-in-progress` since 2026-09-21, with the reasoning written
next to it ("Cancelling a superseded *pull-request* run is always right, since the newer head is the
one being judged"). `pr-checks.yml` is the heavier of the two — the `audit` job runs the whole Python
suite with coverage, ~21 minutes — and it had no `concurrency` block at all. Nothing noticed, because
a missing concurrency group produces no failure: the run is simply still going.

Why this is safe to cancel, where the D1 writers are not
--------------------------------------------------------
`cancel-in-progress: true` is right here and wrong there for one reason: this job **only reports**.
`sync-d1.yml` and its siblings mutate a corpus mid-flight, so cancelling one interrupts an import
(`tests/test_secret_scoping.py` pins `cancel-in-progress: false` on those). The audit writes nothing
that outlives it, and the run being cancelled is judging a commit nobody will merge any more.

What could go wrong with the key, and how it is avoided
------------------------------------------------------
`head_ref` is a branch *name*, which two forks can both use (`fix/typo`); keying on it would let one
fork's pull request cancel another's. The key therefore uses `pull_request.number`, with
`github.run_id` as the fallback so a manual dispatch — which has no pull request — never joins
someone else's group. `cancel-in-progress` is gated on `event_name == 'pull_request'` for the same
reason: a human asking for a run should get that run.
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
WORKFLOW = REPO / ".github" / "workflows" / "pr-checks.yml"


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_the_audit_declares_a_concurrency_group():
    """The whole file, because the failure this prevents is a block that is simply absent."""
    block = _workflow().get("concurrency")
    assert isinstance(block, dict), (
        "pr-checks.yml has no `concurrency:` block, so every superseded push keeps a 21-minute "
        "audit running to the end — measured at 1,749 wasted runner-minutes over 100 runs")
    assert block.get("group"), "the concurrency block has no group, which is the same as not having one"


def test_a_superseded_pull_request_run_is_cancelled():
    block = _workflow()["concurrency"]
    assert block.get("cancel-in-progress") == "${{ github.event_name == 'pull_request' }}", (
        "`cancel-in-progress` must be true for pull requests and false otherwise — a conditional "
        "expression, not a bare `true`: a manual dispatch has no newer head to supersede it"
    )


def test_the_key_is_per_pull_request_not_per_branch_name():
    """`head_ref` is a branch name; two forks can both use one, and then they cancel each other."""
    group = "".join(str(_workflow()["concurrency"]["group"]).split())
    assert "github.event.pull_request.number" in group, (
        f"the group key is {group!r}: keying on `head_ref` lets one fork's pull request cancel "
        "another fork's, because branch names are not unique across repositories")
    assert "github.run_id" in group, (
        "the key needs a fallback for `workflow_dispatch`, where `pull_request.number` is empty — "
        "without one, every dispatch on the repository shares a single group")


def test_the_reasoning_is_written_next_to_the_key():
    """This repository deletes unexplained blocks; a number in the comment is what stops that."""
    text = WORKFLOW.read_text(encoding="utf-8")
    head = text.split("jobs:", 1)[0]
    assert "1,749" in head, (
        "the measured cost (1,749 runner-minutes over 100 runs) is what makes this block load-bearing "
        "rather than cosmetic; keep it next to the key")
    assert "ci-cross-platform" in head, (
        "the sibling workflow is the precedent that settles the argument; name it")
