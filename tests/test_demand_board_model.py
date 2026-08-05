#!/usr/bin/env python3
"""Test demand board data model — states, override, aggregation.

Covers v2.13.0 release blocker #5 (demand board states) and #6 (maintainer override).
"""
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.demand_board import (
    VALID_CATEGORIES,
    VALID_STATES,
    get_summary,
    list_items,
    load_board,
    normalize_family,
    override_item,
    record_signal,
    save_board,
)


@pytest.fixture(autouse=True)
def temp_board(tmp_path):
    """Use a temporary board file for each test."""
    board_file = tmp_path / "demand-board.jsonl"
    with patch("scripts.demand_board.BOARD_FILE", board_file):
        yield board_file


# ── Family normalization ──

class TestNormalizeFamily:
    def test_known_family(self):
        assert normalize_family("python-env") == "python-env"

    def test_unknown_family(self):
        assert normalize_family("random-garbage") == "unclassified"

    def test_empty(self):
        assert normalize_family("") == "unclassified"


# ── Record signal ──

class TestRecordSignal:
    def test_basic_record(self):
        item = record_signal("python-env", "pip timeout", "curl")
        assert item["family"] == "python-env"
        assert item["reason"] == "pip timeout"
        assert item["source"] == "curl"
        assert item["state"] == "new"
        assert item["count"] == 1
        assert item["category"] == "unknown"

    def test_duplicate_aggregation(self):
        item1 = record_signal("python-env", "pip timeout", "curl")
        item2 = record_signal("python-env", "pip timeout", "mcp")
        assert item1["id"] == item2["id"]
        assert item2["count"] == 2

    def test_different_reason_separate(self):
        item1 = record_signal("python-env", "pip timeout")
        item2 = record_signal("python-env", "ssl error")
        assert item1["id"] != item2["id"]

    def test_reason_truncated(self):
        item = record_signal("test", "x" * 500)
        assert len(item["reason"]) == 200

    def test_category_set(self):
        item = record_signal("test", reason="", source="", category="lesson")
        assert item["category"] == "lesson"

    def test_invalid_category_fallback(self):
        item = record_signal("test", category="bogus")
        assert item["category"] == "unknown"


# ── States ──

class TestStates:
    def test_valid_states(self):
        assert VALID_STATES == {"new", "reviewed", "routed", "rejected"}

    def test_initial_state_is_new(self):
        item = record_signal("test", "reason")
        assert item["state"] == "new"


# ── Maintainer override ──

class TestOverride:
    def test_override_state(self):
        item = record_signal("test", "reason")
        updated = override_item(item["id"], state="reviewed")
        assert updated["state"] == "reviewed"
        assert len(updated["override_history"]) == 1
        assert updated["override_history"][0]["old_state"] == "new"
        assert updated["override_history"][0]["new_state"] == "reviewed"

    def test_override_category(self):
        item = record_signal("test", "reason")
        updated = override_item(item["id"], category="lesson")
        assert updated["category"] == "lesson"

    def test_override_both(self):
        item = record_signal("test", "reason")
        updated = override_item(item["id"], state="routed", category="bug", note="confirmed bug")
        assert updated["state"] == "routed"
        assert updated["category"] == "bug"
        assert updated["override_history"][0]["note"] == "confirmed bug"

    def test_override_invalid_state_ignored(self):
        item = record_signal("test", "reason")
        updated = override_item(item["id"], state="bogus")
        assert updated["state"] == "new"  # unchanged

    def test_override_not_found(self):
        result = override_item("nonexistent", state="reviewed")
        assert result is None

    def test_override_history_accumulates(self):
        item = record_signal("test", "reason")
        override_item(item["id"], state="reviewed")
        updated = override_item(item["id"], state="routed")
        assert len(updated["override_history"]) == 2


# ── List items ──

class TestListItems:
    def test_list_all(self):
        record_signal("a", "r1")
        record_signal("b", "r2")
        items = list_items()
        assert len(items) == 2

    def test_filter_by_state(self):
        item = record_signal("test", "r1")
        record_signal("test", "r2")
        override_item(item["id"], state="reviewed")
        reviewed = list_items(state="reviewed")
        assert len(reviewed) == 1

    def test_filter_by_family(self):
        record_signal("python-env", "r1")
        record_signal("npm-publish", "r2")
        items = list_items(family="python-env")
        assert len(items) == 1


# ── Summary ──

class TestSummary:
    def test_empty_board(self):
        summary = get_summary()
        assert summary["total"] == 0

    def test_summary_counts(self):
        record_signal("python-env", "r1")
        record_signal("python-env", "r2")
        record_signal("npm-publish", "r3")
        summary = get_summary()
        assert summary["total"] == 3
        assert summary["by_family"]["python-env"] == 2
        assert summary["by_family"]["npm-publish"] == 1

    def test_summary_by_state(self):
        item = record_signal("test", "r1")
        record_signal("test", "r2")
        override_item(item["id"], state="reviewed")
        summary = get_summary()
        assert summary["by_state"]["new"] == 1
        assert summary["by_state"]["reviewed"] == 1


# ── Persistence ──

class TestPersistence:
    def test_save_and_load(self):
        record_signal("test", "r1")
        items = load_board()
        assert len(items) == 1
        assert items[0]["reason"] == "r1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
