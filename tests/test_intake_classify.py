#!/usr/bin/env python3
"""Test intake classifier — routing from intake to demand board.

Covers v2.13.0 release blocker #4 (classifier constrained output).
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.intake_classify import classify, process_entry


@pytest.fixture(autouse=True)
def temp_board(tmp_path):
    """Use a temporary demand board file."""
    board_file = tmp_path / "demand-board.jsonl"
    with patch("scripts.demand_board.BOARD_FILE", board_file):
        yield board_file


# ── Classification ──

class TestClassify:
    def test_explicit_lesson(self):
        assert classify({"type": "lesson_candidate"}) == "lesson"

    def test_explicit_bug(self):
        assert classify({"type": "bug"}) == "bug"

    def test_explicit_diagnostic(self):
        assert classify({"type": "diagnostic"}) == "rescue"

    def test_explicit_friction(self):
        assert classify({"type": "friction"}) == "rescue"

    def test_explicit_noise(self):
        assert classify({"type": "noise"}) == "noise"

    def test_keyword_lesson(self):
        assert classify({"message": "I fixed it by adding retry logic"}) == "lesson"

    def test_keyword_bug(self):
        assert classify({"message": "misakanet search returns 500 error"}) == "bug"

    def test_keyword_rescue(self):
        assert classify({"message": "I'm stuck, pip install fails with timeout"}) == "rescue"

    def test_positive_feedback_noise(self):
        assert classify({"feedback": "helpful"}) == "noise"

    def test_empty_is_noise(self):
        assert classify({}) == "noise"

    def test_unknown_type_keyword_fallback(self):
        assert classify({"message": "the fix was to add --no-cache"}) == "lesson"


# ── Process entry → demand board ──

class TestProcessEntry:
    def test_lesson_routes_to_demand_board(self):
        cat, family = process_entry({"type": "lesson_candidate", "message": "solved it"})
        assert cat == "lesson"
        assert family == "lesson-feedback"

    def test_bug_routes_to_demand_board(self):
        cat, family = process_entry({"type": "bug", "message": "search crashes"})
        assert cat == "bug"
        assert family == "bug-report"

    def test_noise_skipped(self):
        cat, family = process_entry({"type": "noise"})
        assert cat == "noise"
        assert family == "skipped"

    def test_rescue_routes_to_unclassified(self):
        cat, family = process_entry({"type": "diagnostic", "message": "stuck"})
        assert cat == "rescue"
        assert family == "unclassified"


# ── Constrained output ──

class TestConstrainedOutput:
    """v2.13.0 requirement: classifier output constrained to lesson/rescue/bug/noise."""

    def test_all_categories_valid(self):
        valid = {"lesson", "rescue", "bug", "noise"}
        test_cases = [
            {"type": "lesson_candidate"},
            {"type": "bug"},
            {"type": "diagnostic"},
            {"type": "friction"},
            {"type": "noise"},
            {"message": "fixed it"},
            {"message": "broken"},
            {"message": "help stuck"},
            {},
        ]
        for entry in test_cases:
            cat = classify(entry)
            assert cat in valid, f"classify({entry}) = {cat}, not in {valid}"

    def test_no_crash_on_malformed(self):
        """Classifier should never crash, even on bad input."""
        bad_inputs = [
            {"type": None},
            {"message": ""},
            {"type": 123},
            {"random": "garbage"},
        ]
        for entry in bad_inputs:
            cat = classify(entry)
            assert cat in {"lesson", "rescue", "bug", "noise"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
