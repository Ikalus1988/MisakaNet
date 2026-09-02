#!/usr/bin/env python3
"""Unit and integration tests for PR Genius stats computation and export."""

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from scripts.pr_genius_stats import (
    classify_pr_type,
    calculate_run_latency_seconds,
    compute_metrics_for_window,
    build_stats_payload,
)


class TestPRGeniusStats(unittest.TestCase):
    def setUp(self):
        self.sample_runs = [
            {
                "id": 1,
                "name": "PR Quality Gate",
                "path": ".github/workflows/pr-quality-gate.yml",
                "display_title": "feat(core): add new search ranking logic",
                "conclusion": "success",
                "created_at": "2026-08-15T10:00:00Z",
                "updated_at": "2026-08-15T10:00:10Z",
                "run_started_at": "2026-08-15T10:00:00Z",
                "head_commit": {"message": "feat: ranking"},
            },
            {
                "id": 2,
                "name": "PR Quality Gate",
                "path": ".github/workflows/pr-quality-gate.yml",
                "display_title": "docs(lessons): add python async lesson",
                "conclusion": "success",
                "created_at": "2026-08-14T10:00:00Z",
                "updated_at": "2026-08-14T10:00:15Z",
                "run_started_at": "2026-08-14T10:00:00Z",
                "head_commit": {"message": "docs: lesson"},
            },
            {
                "id": 3,
                "name": "PR Quality Gate",
                "path": ".github/workflows/pr-quality-gate.yml",
                "display_title": "fix(cli): handle missing token gracefully",
                "conclusion": "failure",
                "created_at": "2026-08-10T10:00:00Z",
                "updated_at": "2026-08-10T10:00:20Z",
                "run_started_at": "2026-08-10T10:00:00Z",
                "head_commit": {"message": "fix: error"},
            },
            {
                "id": 4,
                "name": "PR Quality Gate",
                "path": ".github/workflows/pr-quality-gate.yml",
                "display_title": "chore(deps): bump actions/checkout",
                "conclusion": "skipped",
                "created_at": "2026-07-01T10:00:00Z",
                "updated_at": "2026-07-01T10:00:05Z",
                "run_started_at": "2026-07-01T10:00:00Z",
                "head_commit": {"message": "chore: bump"},
            },
        ]

    def test_classify_pr_type(self):
        self.assertEqual(classify_pr_type("feat(core): add feature"), "code")
        self.assertEqual(classify_pr_type("docs: update README"), "docs")
        self.assertEqual(classify_pr_type("docs/lessons: new lesson"), "docs")
        self.assertEqual(classify_pr_type("feat(docs): add automated doc generator script"), "mixed")

    def test_calculate_run_latency(self):
        run = {
            "created_at": "2026-08-15T12:00:00Z",
            "updated_at": "2026-08-15T12:00:12Z",
            "run_started_at": "2026-08-15T12:00:00Z",
        }
        self.assertEqual(calculate_run_latency_seconds(run), 12.0)

    def test_compute_metrics_windows(self):
        now = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
        m7d = compute_metrics_for_window(self.sample_runs, now, days=7)
        self.assertEqual(m7d["total_runs"], 3)
        self.assertEqual(m7d["status_counts"]["success"], 2)
        self.assertEqual(m7d["status_counts"]["failure"], 1)
        self.assertAlmostEqual(m7d["success_rate"], 66.67, places=2)
        self.assertEqual(m7d["median_latency_seconds"], 15.0)

        m_all = compute_metrics_for_window(self.sample_runs, now, days=None)
        self.assertEqual(m_all["total_runs"], 4)
        self.assertEqual(m_all["status_counts"]["skipped"], 1)

    def test_build_stats_payload(self):
        now = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)
        payload = build_stats_payload(self.sample_runs, repo="Ikalus1988/MisakaNet", generated_at=now)
        self.assertIn("summary", payload)
        self.assertIn("windows", payload)
        self.assertIn("7d", payload["windows"])
        self.assertIn("30d", payload["windows"])
        self.assertIn("all_time", payload["windows"])
        self.assertEqual(payload["summary"]["total_observed_runs"], 4)

    def test_generated_json_file(self):
        json_path = Path("data/pr-genius-stats.json")
        self.assertTrue(json_path.exists(), "data/pr-genius-stats.json should exist")
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertIn("windows", data)
            self.assertIn("all_time", data["windows"])


if __name__ == "__main__":
    unittest.main()
