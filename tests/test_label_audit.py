#!/usr/bin/env python3
"""The label audit's two failure shapes: a misfiled product issue and a duplicated label axis."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import label_audit  # noqa: E402


def issue(number: int, *labels: str) -> dict:
    return {"number": number, "title": f"#{number}", "labels": [{"name": name} for name in labels]}


def test_a_corpus_queue_label_on_a_product_issue_is_a_leak():
    result = label_audit.audit([issue(1, "needs-human-review", "scope:repo")])
    assert result["leaks"] == [1]


def test_a_corpus_intake_is_not_a_leak():
    result = label_audit.audit([issue(2, "mcp-intake", "needs-human-review")])
    assert result["leaks"] == []


def test_an_escalated_decision_is_reported_separately():
    result = label_audit.audit([issue(3, "mcp-intake", "decision")])
    assert result["escalated_intakes"] == [3]
    assert result["leaks"] == []


def test_two_labels_for_the_same_axis_are_reported():
    result = label_audit.audit([issue(4, "intake"), issue(5, "mcp-intake")])
    assert "intake / mcp-intake" in result["duplicate_aliases"]


def test_a_needs_info_waiting_on_a_reporter_is_corpus_only():
    """`needs-info` (2026-11-12) marks an intake that is waiting for its Root Cause, so a product
    issue carrying it is the same misfile as a `needs-human-review` one."""
    assert label_audit.audit([issue(7, "needs-info", "scope:repo")])["leaks"] == [7]
    assert label_audit.audit([issue(8, "mcp-intake", "needs-info")])["leaks"] == []


def test_an_approval_watch_tracker_is_not_a_misfile():
    """`approval-watch.yml` writes `needs-human-review` to mean "a human must approve a run"."""
    result = label_audit.audit([issue(6, "needs-human-review", "approval-watch", "needs-ac")])
    assert result["leaks"] == []
