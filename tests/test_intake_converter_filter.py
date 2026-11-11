#!/usr/bin/env python3
"""The batch converter's intake filter must skip `[Intake]` issues that escalated to a decision.

Measured on 2026-11-10: 190 open `mcp-intake` issues, two of them (#4639, #4629) also carry
`decision` — they are questions for the owner, not lessons. The converter used to filter on the title
alone, so a structured decision intake would have been published as advice.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import convert_intake_batch as batch  # noqa: E402


def issue(title: str, *labels: str) -> dict:
    return {"title": title, "labels": [{"name": name} for name in labels]}


def test_a_plain_intake_is_convertible():
    assert batch.is_convertible(issue("[Intake] pip timeout behind proxy", "mcp-intake"))


def test_a_decision_intake_is_not_convertible():
    assert not batch.is_convertible(issue("[Intake] should we do X?", "mcp-intake", "decision"))


def test_a_non_intake_title_is_not_convertible():
    assert not batch.is_convertible(issue("[Question] pip timeout", "mcp-intake"))


def test_missing_labels_do_not_crash_the_filter():
    assert batch.is_convertible({"title": "[Intake] x", "labels": []})
    assert batch.is_convertible({"title": "[Intake] x"})
