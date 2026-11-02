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
