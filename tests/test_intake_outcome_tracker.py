"""Tests for privacy-preserving intake outcome tracker (Issue #1093)."""

import json
import tempfile
import unittest
from pathlib import Path

from scripts.intake_outcome_tracker import compute_outcomes, load_queue


class TestIntakeOutcomeTracker(unittest.TestCase):
    def setUp(self):
        self.sample_records = [
            {"type": "lesson", "status": "accepted", "source": "github"},
            {"type": "bug", "status": "converted", "source": "slack"},
            {"type": "noise", "status": "rejected", "source": "github"},
            {"type": "lesson", "status": "pending", "source": "discord"},
            {"type": "bug", "status": "accepted", "source": "github"},
        ]

    def test_empty_queue(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            path = Path(f.name)
        records = load_queue(path)
        outcomes = compute_outcomes(records)
        self.assertEqual(outcomes["total_submitted"], 0)
        self.assertEqual(outcomes["total_reviewed"], 0)
        self.assertEqual(outcomes["total_pending"], 0)
        self.assertEqual(outcomes["conversion_rate"], 0.0)
        path.unlink()

    def test_compute_outcomes(self):
        outcomes = compute_outcomes(self.sample_records)
        self.assertEqual(outcomes["total_submitted"], 5)
        self.assertEqual(outcomes["total_reviewed"], 4)
        self.assertEqual(outcomes["total_pending"], 1)
        self.assertEqual(outcomes["conversion_rate"], 0.25)  # 1 converted / 4 reviewed

    def test_by_type_counts(self):
        outcomes = compute_outcomes(self.sample_records)
        self.assertEqual(outcomes["by_type"]["lesson"], 2)
        self.assertEqual(outcomes["by_type"]["bug"], 2)
        self.assertEqual(outcomes["by_type"]["noise"], 1)

    def test_by_status_counts(self):
        outcomes = compute_outcomes(self.sample_records)
        self.assertEqual(outcomes["by_status"]["accepted"], 2)
        self.assertEqual(outcomes["by_status"]["converted"], 1)
        self.assertEqual(outcomes["by_status"]["rejected"], 1)
        self.assertEqual(outcomes["by_status"]["pending"], 1)

    def test_by_source_counts(self):
        outcomes = compute_outcomes(self.sample_records)
        self.assertEqual(outcomes["by_source"]["github"], 3)
        self.assertEqual(outcomes["by_source"]["slack"], 1)
        self.assertEqual(outcomes["by_source"]["discord"], 1)

    def test_no_private_text_stored(self):
        """Verify no message or text fields appear in output."""
        records_with_text = [
            {"type": "bug", "status": "accepted", "message": "This is private user text"},
        ]
        outcomes = compute_outcomes(records_with_text)
        outcome_str = json.dumps(outcomes)
        self.assertNotIn("private user text", outcome_str)
        self.assertNotIn("message", outcome_str)

    def test_conversion_rate_all_reviewed(self):
        records = [
            {"type": "bug", "status": "converted"},
            {"type": "bug", "status": "accepted"},
        ]
        outcomes = compute_outcomes(records)
        self.assertEqual(outcomes["conversion_rate"], 0.5)

    def test_conversion_rate_no_reviewed(self):
        records = [
            {"type": "bug", "status": "pending"},
        ]
        outcomes = compute_outcomes(records)
        self.assertEqual(outcomes["conversion_rate"], 0.0)

    def test_load_queue_missing_file(self):
        path = Path("/nonexistent/file.jsonl")
        records = load_queue(path)
        self.assertEqual(records, [])

    def test_load_queue_invalid_json(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write("not json\n")
            f.write("also not json\n")
            path = Path(f.name)
        records = load_queue(path)
        self.assertEqual(records, [])
        path.unlink()


if __name__ == "__main__":
    unittest.main()
