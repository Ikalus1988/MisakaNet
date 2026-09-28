#!/usr/bin/env python3
"""The weekly intake-kind audit must be able to *fire* — and its cleanup branch must be reachable.

Issue #1826 listed `intake-kind-audit.yml` among the automations whose useful branch never executes:
three scheduled runs, three "clean", zero digest issues. Its own reading was that `:36` greps the digest
for a fixed sentence and therefore always concludes "clean". That inference was half right:

* the grep is fine **if** the digest sentence is the one the workflow looks for — a contract nothing
  checked, and one that breaks silently the moment either side is reworded;
* and `find_flagged()` — the function that decides whether there is anything to report — had **no test at
  all**. So "no misfiles found" and "the detector never fires" produced the same output, which is the
  condition this repository treats as a defect rather than a verdict.

Rerun against the live corpus on 2026-09-25 (`--labels mcp-intake --state open --digest`, 37 issues):
still clean. That is now a *finding* rather than an assumption, because these tests show the detection
path firing on fixtures and the two halves of the contract agreeing.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.audit_intake_kinds import find_flagged, render_digest  # noqa: E402

WORKFLOW = REPO / ".github" / "workflows" / "intake-kind-audit.yml"
# The sentence the workflow greps to decide "nothing to report".
CLEAN_SENTENCE = "No flagged question/lesson misfiles found"


def _row(number=1, kind_body="missing_lesson", labels=("mcp-intake",), auto=False) -> dict:
    return {"number": number, "title": "t", "state": "open", "labels": list(labels),
            "kind_body": kind_body, "kind_detected": kind_body, "auto_detected": auto,
            "problem_preview": "p"}


# ── the detection path, which had never been shown to execute ───────────────────────
def test_question_content_that_was_auto_rejected_is_flagged():
    """The #1396 dead end: content reads as a question, the old pipeline rejected it as a lesson."""
    rows = [_row(1, labels=("mcp-intake", "auto-rejected"), auto=True)]
    assert find_flagged(rows) == [(rows[0], "question-content-auto-rejected")]


def test_an_explicit_question_that_was_auto_rejected_is_flagged():
    rows = [_row(2, kind_body="question", labels=("mcp-intake", "auto-rejected"))]
    assert find_flagged(rows) == [(rows[0], "explicit-question-auto-rejected")]


def test_a_question_without_the_question_label_is_flagged():
    """Routing did not finish: the body says question, the labels never caught up."""
    rows = [_row(3, kind_body="question", labels=("mcp-intake", "needs-human-review"))]
    assert find_flagged(rows) == [(rows[0], "explicit-question-unlabeled")]


def test_clean_rows_are_not_flagged():
    """The other direction, or the digest is noise on every run."""
    rows = [
        _row(4, kind_body="missing_lesson", labels=("mcp-intake", "intake")),
        _row(5, kind_body="question", labels=("mcp-intake", "question", "type:question")),
        _row(6, kind_body="missing_lesson", labels=("mcp-intake", "auto-rejected")),   # rejected, but
    ]                                                                                  # not question-y
    assert find_flagged(rows) == []


def test_the_first_matching_reason_wins_and_rows_are_not_duplicated():
    """One row can satisfy two conditions; the digest must not list it twice."""
    rows = [_row(7, kind_body="question", labels=("mcp-intake", "auto-rejected"), auto=True)]
    flagged = find_flagged(rows)
    assert len(flagged) == 1, flagged
    assert flagged[0][1] == "question-content-auto-rejected", flagged


# ── the contract between the script and the workflow's grep ─────────────────────────
def test_the_workflow_greps_for_the_sentence_the_digest_actually_prints():
    """`intake-kind-audit.yml` decides "clean" by grepping this sentence. Nothing checked the two
    halves agreed, and a reword on either side turns the audit into a permanent "clean"."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert f'grep -q "{CLEAN_SENTENCE}"' in text, text[-400:]
    assert CLEAN_SENTENCE in render_digest([]), render_digest([])


def test_a_non_empty_digest_never_contains_the_clean_sentence():
    """Otherwise a run with findings would be read as clean — the failure mode #1826 suspected."""
    rows = [_row(8, kind_body="question", labels=("mcp-intake",))]
    digest = render_digest(find_flagged(rows))
    assert CLEAN_SENTENCE not in digest, digest
    assert "# 🧭 Intake Kind Audit" in digest
    assert "#8" in digest, "the digest must name the issue it is asking somebody to reconcile"


def test_the_digest_names_a_reason_for_every_row():
    rows = [_row(9, auto=True, labels=("mcp-intake", "auto-rejected")),
            _row(10, kind_body="question", labels=("mcp-intake",))]
    digest = render_digest(find_flagged(rows))
    assert "question-content-auto-rejected" in digest
    assert "explicit-question-unlabeled" in digest


def test_the_audit_is_scheduled_and_can_be_run_by_hand():
    """Every claim in #1826 was settled by a real run, so the entry point has to exist."""
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    triggers = workflow.get("on") or workflow.get(True)
    assert "schedule" in triggers, triggers
    assert "workflow_dispatch" in triggers, triggers
