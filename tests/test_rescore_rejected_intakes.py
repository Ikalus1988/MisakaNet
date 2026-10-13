#!/usr/bin/env python3
"""The re-score's decision logic, pinned without touching GitHub.

A scorer fix is forward-only — `intake-auto-review.yml` runs on `issues: [opened, reopened]`
and nothing revisits an issue that already carries `auto-rejected`. Measured 2026-10-13: three
of the twenty-five open rejected intakes score `review` under current rules, and two of those
are the issues the scorer defects were diagnosed from (#3080, #3192). This script is the
follow-through, so its decision logic has to be right without a network round-trip to find out.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "rescore_rejected_intakes.py"
WORKFLOW = REPO / ".github" / "workflows" / "intake-auto-review.yml"


def _load():
    spec = importlib.util.spec_from_file_location("rescore_rejected_intakes", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


RESCORE = _load()


def test_a_verdict_that_no_longer_rejects_is_planned_as_a_relabel():
    issues = [{"number": 1, "title": "t", "body": "b"}, {"number": 2, "title": "t", "body": "b"}]
    verdicts = {1: ("reject", 30.0), 2: ("review", 45.8)}

    changes = RESCORE.plan(issues, lambda n, t, b: verdicts[n])

    assert [c["number"] for c in changes] == [2], "a still-rejecting verdict must not be touched"
    change = changes[0]
    assert change["add"] == ["needs-human-review"]
    assert "auto-rejected" in change["remove"], "the stale verdict is what has to go"
    assert "needs-salvage" in change["remove"], (
        "needs-salvage is a reject-side label; leaving it would move the stale verdict sideways "
        "instead of clearing it")


def test_an_approving_verdict_gets_the_workflows_own_labels():
    changes = RESCORE.plan([{"number": 7, "title": "t", "body": "b"}], lambda n, t, b: ("approve", 80.0))
    assert changes[0]["add"] == ["auto-approved", "needs-human-review"]


def test_all_four_verdict_labels_are_cleared_before_the_new_one_is_applied():
    """Otherwise an issue can end up carrying `auto-rejected` and `auto-approved` at once."""
    for decision in ("approve", "review", "reject"):
        remove, _ = RESCORE.label_changes(decision)
        assert set(RESCORE.CLEARED_LABELS) <= set(remove), decision


def test_the_mapping_only_uses_labels_the_workflow_already_knows():
    """A rename in the workflow must break this, not silently relabel issues to nothing."""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    used = set(RESCORE.CLEARED_LABELS) | {RESCORE.SALVAGE_LABEL}
    for decision in ("approve", "review", "reject"):
        remove, add = RESCORE.label_changes(decision)
        used |= set(remove) | set(add)
    missing = sorted(label for label in used if f'"{label}"' not in workflow)
    assert not missing, f"labels this script applies are absent from {WORKFLOW.name}: {missing}"
