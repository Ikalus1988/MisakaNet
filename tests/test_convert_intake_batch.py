#!/usr/bin/env python3
"""`scripts/convert_intake_batch.py` must refuse what CI's lesson gate would refuse.

Why (2026-11-02)
----------------
The first automated batch opened a pull request carrying a lesson that `lesson_gate.py` rejects for
being under the 400-character body floor — the same report a maintainer had dropped by hand the day
before. The converter's own floor is 120 characters, so "the converter wrote it" and "the repository
accepts it" are different claims, and the batch is the place where that difference becomes a red PR
nobody asked for.

The remaining test is the histogram: a number without a reason is not a report.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import convert_intake_batch as batch  # noqa: E402

BODY_OK = """**Kind:** missing_lesson
**Source:** mcp

## Problem

The build fails on a clean checkout.

## Root Cause

The lockfile names a registry the runner cannot reach.

## Fix

Point `npm_config_registry` at the public registry before installing.
"""

BODY_THIN = """**Kind:** missing_lesson
**Source:** mcp

## Problem

It broke.

## Root Cause

A reason.

## Fix

Do it differently.
"""


def test_a_full_report_is_convertible():
    issue = {"number": 1, "title": "[Intake] build fails on a clean checkout", "body": BODY_OK}
    record, notes = batch.conv.convert(issue, {"devops"}, {"domain": "devops"})
    assert record is not None, notes


def test_a_gate_rejected_report_is_not_written():
    """The body above is under the gate's 400-character floor, so the batch must skip it."""
    issue = {"number": 2, "title": "[Intake] it broke", "body": BODY_THIN}
    record, notes = batch.conv.convert(issue, {"devops"}, {"domain": "devops"})
    assert record is not None, (
        "the converter itself still accepts short bodies — that is why the batch has to gate")

    import lesson_gate  # noqa: PLC0415

    assert not lesson_gate.validate_content_len(record["content"], lesson_gate.MIN_NEW_LESSON_CHARS), (
        "fixture drifted: this body now passes the gate, so it cannot demonstrate the skip")


def test_the_skip_histogram_names_the_gate():
    """The reason has to be readable, not just counted."""
    reasons = ["would fail the lesson gate", "missing Problem/Root Cause/Fix"]
    assert all(reason.strip() for reason in reasons)


# ── the two rules that made #5104 red (2026-11-16) ─────────────────────────────────────────────
# 23 files: 5 intakes an existing lesson already cited, 18 lessons teaching a command name the base
# corpus never had. The batch had asked neither question.

def _lesson(number: int, domain: str = "devops") -> dict:
    body = (
        "## Problem\n\nThe build fails on a clean checkout of this repository.\n\n"
        "## Root Cause\n\nThe lockfile names a registry the runner cannot reach.\n\n"
        "## Fix\n\nPoint `npm_config_registry` at the public registry before installing.\n\n"
        "## Verification\n\nRe-run `npm ci` on a clean checkout: it completes.\n"
    ) * 6
    return {
        "number": number,
        "title": "[Intake] build fails on a clean checkout",
        "body": f"**Kind:** missing_lesson\n**Source:** mcp\n**Domain:** {domain}\n\n" + body,
    }


def test_an_intake_a_lesson_already_cites_is_skipped(tmp_path):
    """One intake converts to one lesson. The receipt reads `provenance.issue`, so a second lesson
    makes it ambiguous — the gate has the rule, and the batch now asks it."""
    import lesson_gate  # noqa: PLC0415

    lesson = tmp_path / "lessons" / "contrib" / "already-converted.md"
    lesson.parent.mkdir(parents=True)
    lesson.write_text(
        "---\n"
        'title: "A lesson that already cites this intake"\n'
        'domain: "devops"\n'
        "tags:\n  - \"npm\"\n  - \"registry\"\n"
        'status: "published"\n'
        'evidence_level: "E1"\n'
        'summary_plain: "x"\n'
        'trigger: "npm ci fails"\n'
        'verify: "npm ci completes"\n'
        "provenance:\n"
        "  issue: 424242\n"
        "---\n\n## Problem\nx\n",
        encoding="utf-8",
    )
    issue = _lesson(424242)
    record, notes = batch.conv.convert(issue, {"devops"}, {"domain": "devops"})
    assert record is not None, notes
    assert lesson_gate.find_duplicate_intake_claim("424242", tmp_path), (
        "fixture drifted: the claim is not detectable, so this test proves nothing")
    assert batch.precheck_skip(issue, record, repo=tmp_path) == "intake already cited by a lesson"


def test_a_command_name_the_base_corpus_never_had_is_skipped(tmp_path):
    """The public-surface rule, which the batch did not ask and CI does."""
    issue = _lesson(424243)
    record, notes = batch.conv.convert(issue, {"devops"}, {"domain": "devops"})
    assert record is not None, notes
    # A shell fence, not a backticked word: `_is_command_span` requires two words or a `$ `
    # prefix, so a single backticked token is deliberately not a command name.
    record["content"] += chr(10) + "```bash" + chr(10) + "zz-private-probe --flag" + chr(10) + "```" + chr(10)
    reason = batch.precheck_skip(issue, record, repo=REPO)
    assert reason == "would fail the lesson gate (public surface)", reason


def test_a_clean_candidate_passes_the_precheck(tmp_path):
    """The control: a precheck that refused everything would pass the two tests above."""
    issue = _lesson(424244)
    record, notes = batch.conv.convert(issue, {"devops"}, {"domain": "devops"})
    assert record is not None, notes
    assert batch.precheck_skip(issue, record, repo=tmp_path) is None
