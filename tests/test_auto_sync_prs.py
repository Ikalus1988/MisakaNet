#!/usr/bin/env python3
"""The branch sync must not churn PRs: scheduled, and never pushing to a PR that can already merge.

Why this file exists (2026-10-01)
---------------------------------
`auto-sync-prs.yml` used to run on every push to `main` and merge `main` into every open same-repo PR.
That is defensible for a repository whose ruleset requires up-to-date branches — this one's does not
(`strict_required_status_checks_policy: false`, measured). What it cost instead:

* each sync re-ran the PR's whole cross-platform matrix (30+ checks), with 42 runs queued repo-wide;
* the push **resets GitHub's `mergeable` computation**, so a PR that was about to merge goes back to
  `mergeable_state: unknown` and auto-merge stalls — the 2.40.0 release PR's head moved three times in
  twenty minutes, and #2584 had to be merged through the API because a sync had re-headed it seconds
  before.

So two rules are pinned here, both as functions of the workflow source (a rule that cannot be shown to
fail is a comment, not a gate): the sync is **scheduled, not triggered by every main push**, and it
**skips a PR that is already mergeable**.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

WORKFLOW = REPO / ".github" / "workflows" / "auto-sync-prs.yml"


def source(path: Path | None = None) -> str:
    return (path or WORKFLOW).read_text(encoding="utf-8")


def triggers(spec: dict) -> dict:
    """The `on:` block. A YAML 1.1 loader parses the bare key `on` as the boolean True."""
    return spec.get("on") or spec.get(True) or {}


def per_push_problems(text: str) -> list[str]:
    """Rule 1: a push trigger on this workflow is the churn this file exists to prevent."""
    spec = yaml.safe_load(text)
    block = triggers(spec if isinstance(spec, dict) else {})
    problems = []
    if "push" in block:
        problems.append("the sync is triggered by pushes again: every main push re-heads every open PR")
    if "schedule" not in block:
        problems.append("no schedule: nothing syncs the branches at a controlled cadence")
    if "workflow_dispatch" not in block:
        problems.append("no workflow_dispatch: a human cannot ask for a sync")
    return problems


def minimum_interval_hours(cron: str) -> float:
    """The smallest gap the cron can produce, from its hour field (`*/N`, a fixed hour, or `*`)."""
    fields = cron.split()
    assert len(fields) == 5, f"not a five-field cron: {cron!r}"
    hour = fields[1]
    if hour == "*":
        return 1.0
    stepped = re.fullmatch(r"\*/(\d+)", hour)
    if stepped:
        return float(stepped.group(1))
    if re.fullmatch(r"\d+", hour):
        return 24.0
    raise AssertionError(f"unsupported hour field: {hour!r}")


def mergeable_guard_problems(text: str) -> list[str]:
    """Rule 2: the per-PR guard that keeps a mergeable PR out of the loop."""
    return [] if re.search(r'if\s+\[\s*"\$MERGEABLE"\s*=\s*"true"\s*\]', text) else [
        "no `mergeable == true` guard: a PR that can already merge is still pushed to, which resets its "
        "mergeability computation and re-runs its whole matrix"
    ]


def test_the_sync_is_scheduled_and_not_triggered_by_every_main_push():
    block = triggers(yaml.safe_load(source()))
    assert per_push_problems(source()) == [], (block, per_push_problems(source()))
    crons = [entry["cron"] for entry in block["schedule"]]
    assert crons, block
    for cron in crons:
        assert minimum_interval_hours(cron) >= 3, (
            f"{cron} syncs more often than every three hours; six-hourly is what the cost/benefit supports")


def test_a_mergeable_pr_is_never_synced():
    assert mergeable_guard_problems(source()) == []


def test_the_push_rule_can_go_red():
    """The pre-change shape: `on: push` — the gate must say so, not merely lack an opinion."""
    broken = source().replace(
        "on:\n  schedule:\n    - cron: '17 */6 * * *'\n  workflow_dispatch:",
        "on:\n  push:\n    branches: [main]\n  workflow_dispatch:")
    assert broken != source(), "the trigger block moved; this fixture needs the new anchor"
    problems = per_push_problems(broken)
    assert problems, "a push trigger must be a problem"
    assert any("push" in p for p in problems), problems


def test_the_frequency_rule_can_go_red():
    assert minimum_interval_hours("17 */6 * * *") == 6
    assert minimum_interval_hours("0 * * * *") == 1
    assert minimum_interval_hours("0 3 * * *") == 24
    with pytest.raises(AssertionError):
        minimum_interval_hours("17 */6 * *")          # not five fields


def test_the_mergeable_guard_can_go_red():
    """The pre-2026-10-01 shape: the loop skipped only conflicting PRs."""
    broken = source().replace('if [ "$MERGEABLE" = "true" ]; then', 'if [ "$MERGEABLE" = "never" ]; then')
    assert broken != source(), "the guard moved; this fixture needs the new anchor"
    assert mergeable_guard_problems(broken), "a missing mergeable guard must be a problem"
