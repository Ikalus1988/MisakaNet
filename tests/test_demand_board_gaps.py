"""Tests for demand board gap analysis (Issue #1164)."""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.demand_board import get_gap_summary, load_gaps, GAPS_FILE


class TestGapLoading:
    """Test gap data loading."""

    def test_load_empty_gaps(self, tmp_path):
        """No gap file returns empty list."""
        with patch("scripts.demand_board.GAPS_FILE", tmp_path / "nonexistent.jsonl"):
            assert load_gaps() == []

    def test_load_valid_gaps(self, tmp_path):
        """Load valid JSONL gap entries."""
        gap_file = tmp_path / "test_gaps.jsonl"
        entries = [
            {"query": "robot welding error", "timestamp": "2026-08-23T00:00:00Z", "result_count": 0},
            {"query": "servo motor fault", "timestamp": "2026-08-23T00:01:00Z", "result_count": 0},
        ]
        with open(gap_file, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

        with patch("scripts.demand_board.GAPS_FILE", gap_file):
            gaps = load_gaps()
        assert len(gaps) == 2
        assert gaps[0]["query"] == "robot welding error"
        assert gaps[1]["query"] == "servo motor fault"

    def test_load_skips_invalid_json(self, tmp_path):
        """Invalid JSON lines are skipped."""
        gap_file = tmp_path / "test_gaps.jsonl"
        with open(gap_file, "w") as f:
            f.write("not json\n")
            f.write(json.dumps({"query": "valid"}) + "\n")
            f.write("{broken json\n")

        with patch("scripts.demand_board.GAPS_FILE", gap_file):
            gaps = load_gaps()
        assert len(gaps) == 1


class TestGapSummary:
    """Test gap clustering and summary."""

    def test_empty_summary(self, tmp_path):
        """No data returns zero-count summary."""
        with patch("scripts.demand_board.GAPS_FILE", tmp_path / "empty.jsonl"):
            summary = get_gap_summary()
        assert summary["total"] == 0
        assert summary["clusters"] == []

    def test_single_query_cluster(self, tmp_path):
        """Single query forms one cluster."""
        gap_file = tmp_path / "gaps.jsonl"
        entries = [
            {"query": "robot welding error", "timestamp": "2026-08-23T00:00:00Z", "result_count": 0},
            {"query": "robot welding error", "timestamp": "2026-08-23T00:01:00Z", "result_count": 0},
            {"query": "robot welding error", "timestamp": "2026-08-23T00:02:00Z", "result_count": 0},
        ]
        with open(gap_file, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

        with patch("scripts.demand_board.GAPS_FILE", gap_file):
            summary = get_gap_summary()
        assert summary["total"] == 3
        assert summary["unique_queries"] == 1
        assert len(summary["clusters"]) == 1
        assert summary["clusters"][0]["count"] == 3

    def test_similar_queries_clustered(self, tmp_path):
        """Queries with >50% word overlap are clustered."""
        gap_file = tmp_path / "gaps.jsonl"
        entries = [
            {"query": "robot welding error", "timestamp": "2026-08-23T00:00:00Z", "result_count": 0},
            {"query": "robot welding fault", "timestamp": "2026-08-23T00:01:00Z", "result_count": 0},
            {"query": "servo motor error", "timestamp": "2026-08-23T00:02:00Z", "result_count": 0},
            {"query": "servo motor problem", "timestamp": "2026-08-23T00:03:00Z", "result_count": 0},
        ]
        with open(gap_file, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

        with patch("scripts.demand_board.GAPS_FILE", gap_file):
            summary = get_gap_summary()
        assert summary["total"] == 4
        # robot welding error/fault should cluster (2/3 overlap = 0.67)
        # servo motor error/problem should cluster (2/3 overlap = 0.67)
        assert len(summary["clusters"]) == 2

    def test_top_n_limit(self, tmp_path):
        """top parameter limits clusters returned."""
        gap_file = tmp_path / "gaps.jsonl"
        # Use completely distinct queries so they don't cluster
        topics = ["welding", "painting", "assembly", "inspection", "logistics",
                   "conveyor", "robot arm", "sensor", "PLC", "vision system",
                   "hydraulic", "pneumatic", "servo motor", "encoder", "actuator"]
        entries = [
            {"query": t, "timestamp": "2026-08-23T00:00:00Z", "result_count": 0}
            for t in topics
        ]
        with open(gap_file, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

        with patch("scripts.demand_board.GAPS_FILE", gap_file):
            summary = get_gap_summary(top=5)
        assert len(summary["clusters"]) == 5


class TestSearchGapLogging:
    """Test the search handler's gap logging function."""

    def test_log_creates_file(self, tmp_path):
        """Gap log creates the file if it doesn't exist."""
        gap_file = tmp_path / "data" / "search_gaps.jsonl"
        with patch("misakanet.server.handlers.search._GAPS_FILE", gap_file):
            from misakanet.server.handlers.search import _log_search_gap
            _log_search_gap("test query", "test_source")

        assert gap_file.exists()
        with open(gap_file) as f:
            entry = json.loads(f.readline())
        assert entry["query"] == "test query"
        assert entry["source"] == "test_source"
        assert entry["result_count"] == 0

    def test_log_appends(self, tmp_path):
        """Gap log appends to existing file."""
        gap_file = tmp_path / "data" / "search_gaps.jsonl"
        gap_file.parent.mkdir(parents=True, exist_ok=True)

        with patch("misakanet.server.handlers.search._GAPS_FILE", gap_file):
            from misakanet.server.handlers.search import _log_search_gap
            _log_search_gap("query 1", "src1")
            _log_search_gap("query 2", "src2")

        with open(gap_file) as f:
            lines = f.readlines()
        assert len(lines) == 2
        assert json.loads(lines[0])["query"] == "query 1"
        assert json.loads(lines[1])["query"] == "query 2"

    def test_log_silences_errors(self, tmp_path):
        """Gap logging silences I/O errors gracefully."""
        with patch("misakanet.server.handlers.search._GAPS_FILE", Path("/nonexistent/dir/file.jsonl")):
            from misakanet.server.handlers.search import _log_search_gap
            # Should not raise
            _log_search_gap("test", "test")

    def test_log_includes_timestamp(self, tmp_path):
        """Gap entry includes ISO timestamp."""
        gap_file = tmp_path / "data" / "search_gaps.jsonl"
        with patch("misakanet.server.handlers.search._GAPS_FILE", gap_file):
            from misakanet.server.handlers.search import _log_search_gap
            _log_search_gap("test query", "test")

        with open(gap_file) as f:
            entry = json.loads(f.readline())
        assert "timestamp" in entry
        assert "T" in entry["timestamp"]  # ISO format
