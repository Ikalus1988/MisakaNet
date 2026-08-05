#!/usr/bin/env python3
"""Tests for intake digest CLI."""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.intake_digest import (
    _parse_since,
    classify,
    load_intakes,
    summarize,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def sample_queue(tmp_path):
    queue_file = tmp_path / "contribution_queue.jsonl"
    now = datetime.now(timezone.utc).isoformat()
    records = [
        {"id": "c1", "type": "lesson", "status": "pending",
         "source": "cli", "submitted_at": now, "title": "Fix A", "message": "msg A"},
        {"id": "c2", "type": "bug", "status": "accepted",
         "source": "web", "submitted_at": now, "title": "Bug B", "message": "msg B"},
        {"id": "c3", "type": "lesson", "status": "pending",
         "source": "cli", "submitted_at": now, "title": "Fix A", "message": "msg A"},
    ]
    with open(queue_file, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return queue_file


class TestParseSince:
    def test_valid_days(self):
        cutoff = _parse_since("7d")
        assert cutoff is not None
        assert cutoff < datetime.now(timezone.utc)

    def test_valid_hours(self):
        cutoff = _parse_since("12h")
        assert cutoff is not None

    def test_valid_minutes(self):
        cutoff = _parse_since("30m")
        assert cutoff is not None

    def test_invalid_format(self):
        assert _parse_since("foo") is None

    def test_empty(self):
        assert _parse_since("") is None


class TestClassify:
    def test_by_type(self):
        records = [{"type": "lesson"}, {"type": "bug"}, {"type": "lesson"}]
        result = classify(records)
        assert result["by_type"]["lesson"] == 2
        assert result["by_type"]["bug"] == 1

    def test_by_status(self):
        records = [{"status": "pending"}, {"status": "accepted"}]
        result = classify(records)
        assert result["by_status"]["pending"] == 1

    def test_defaults(self):
        result = classify([{}])
        assert result["by_type"]["unknown"] == 1


class TestSummarize:
    def test_pending_count(self, sample_queue):
        records = load_intakes(sample_queue)
        summary = summarize(records)
        assert summary["pending_count"] == 2

    def test_duplicate_groups(self, sample_queue):
        records = load_intakes(sample_queue)
        summary = summarize(records)
        assert len(summary["duplicate_groups"]) == 1

    def test_categories(self, sample_queue):
        records = load_intakes(sample_queue)
        summary = summarize(records)
        assert summary["categories"]["lesson"] == 2
        assert summary["categories"]["bug"] == 1

    def test_total(self, sample_queue):
        records = load_intakes(sample_queue)
        summary = summarize(records)
        assert summary["stats"]["total"] == 3
