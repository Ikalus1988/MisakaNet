"""Tests for privacy-preserving intake outcome tracker (Issue #1093)."""

import json
import tempfile
import unittest
from pathlib import Path

from scripts.intake_outcome_tracker import REPO_ROOT, compute_outcomes, load_queue


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


class TestConversionRateIsHonest(unittest.TestCase):
    """`conversion_rate: 0.0` was quoted as a fact while the corpus proved conversions happened.

    The queue records submissions and nothing updates their status, so `reviewed` is always 0 and
    the rate is always 0.0 — *not observed*, not *measured*. On 2026-09-17 that number was read as
    "no intake ever became a lesson" while 17 lessons carried a `source: mcp-intake-…` marker.
    """

    def test_an_unmaintained_queue_says_so_instead_of_reporting_a_rate(self):
        records = [{"type": "intake", "status": "pending", "source": "mcp-agent"}] * 3
        outcomes = compute_outcomes(records)
        self.assertEqual(outcomes["conversion_rate"], 0.0)
        self.assertFalse(outcomes["conversion_rate_is_observable"])
        self.assertIn("NOT OBSERVABLE", outcomes["conversion_rate_note"])

    def test_a_reviewed_queue_reports_a_measured_rate(self):
        records = [
            {"type": "intake", "status": "converted", "source": "mcp-agent"},
            {"type": "intake", "status": "pending", "source": "mcp-agent"},
        ]
        outcomes = compute_outcomes(records)
        self.assertTrue(outcomes["conversion_rate_is_observable"])
        self.assertEqual(outcomes["conversion_rate"], 1.0)
        self.assertEqual(outcomes["conversion_rate_note"], "measured from the queue")

    def test_the_corpus_side_count_matches_what_the_lessons_say(self):
        """The number that *is* checkable — derived from the corpus, not from a ledger."""
        from scripts.intake_outcome_tracker import corpus_conversions

        corpus = corpus_conversions()
        self.assertGreaterEqual(corpus["lessons"], 10, corpus)
        self.assertEqual(corpus["intakes"], len(set(corpus["intake_ids"])), "ids must be deduped")
        # A four-digit issue number is a real shape here: a `{6,}` bound on the pattern dropped
        # every one of them and undercounted (7 instead of 17, found while writing this).
        self.assertIn("1069", corpus["intake_ids"], corpus["intake_ids"])

    def test_the_queue_and_the_corpus_disagree_by_design(self):
        """If these ever agree, either the ledger got maintained or the corpus stopped converting."""
        outcomes = compute_outcomes(load_queue(Path(REPO_ROOT) / "data" / "contribution_queue.jsonl"))
        if not outcomes["conversion_rate_is_observable"]:
            self.assertGreater(
                outcomes["converted_lessons_in_corpus"], 0,
                "an unobservable rate plus zero corpus conversions would mean the number is right "
                "for the wrong reason",
            )


if __name__ == "__main__":
    unittest.main()
