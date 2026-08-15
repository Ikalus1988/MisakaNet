#!/usr/bin/env python3
"""Unit tests for misakanet trigger metadata schema, annotations, and preflight matcher."""

import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

from scripts.mcp_preflight import evaluate_match, preflight_check, tokenize


class TestLessonTriggers(unittest.TestCase):
    """Test suite for issue #1057 trigger metadata and preflight matching."""

    def setUp(self):
        self.schema_path = REPO_ROOT / "schemas" / "lesson.json"
        self.lessons_path = REPO_ROOT / "data" / "lessons.json"
        self.assertTrue(self.schema_path.exists(), "schemas/lesson.json missing")
        self.assertTrue(self.lessons_path.exists(), "data/lessons.json missing")

        with open(self.schema_path, "r", encoding="utf-8") as f:
            self.schema = json.load(f)

        with open(self.lessons_path, "r", encoding="utf-8") as f:
            self.lessons = json.load(f)

    def test_schema_includes_triggers_field(self):
        """Verify schema defines triggers property with structured fields."""
        props = self.schema.get("properties", {})
        self.assertIn("triggers", props)
        trig_props = props["triggers"].get("properties", {})
        self.assertIn("intents", trig_props)
        self.assertIn("commands", trig_props)
        self.assertIn("environments", trig_props)
        self.assertIn("risks", trig_props)
        self.assertIn("severity", trig_props)
        self.assertEqual(trig_props["severity"].get("enum"), ["low", "medium", "high", "critical"])

    def test_annotated_lessons_in_lessons_json(self):
        """Verify manually annotated lessons have triggers in data/lessons.json."""
        lessons_with_triggers = [l for l in self.lessons if "triggers" in l]
        self.assertGreaterEqual(len(lessons_with_triggers), 5, "At least 5 lessons must be annotated")

        target_ids = {
            "rag-build-strategy-batch",
            "chroma-rebuild-no-checkpoint-cn",
            "wsl2-memory-leak-fix",
            "bge-embedding-fallback-crash",
            "wsl-ntfs-sqlite-update-100x-slower",
        }
        found_ids = {l.get("id") for l in lessons_with_triggers}
        self.assertTrue(target_ids.issubset(found_ids), f"Missing target lessons: {target_ids - found_ids}")

    def test_preflight_critical_rag_match(self):
        """Verify preflight correctly flags critical RAG memory issues."""
        res = preflight_check(
            intent="rag_build vector_index",
            commands=["build_index"],
            environments=["wsl", "gpu"],
        )
        self.assertEqual(res["status"], "warning")
        self.assertEqual(res["risk_level"], "critical")
        self.assertTrue(res["requires_confirmation"])
        self.assertGreaterEqual(res["matched_count"], 1)

        top_rec = res["recommendations"][0]
        self.assertIn(top_rec["id"], ["rag-build-strategy-batch", "chroma-rebuild-no-checkpoint-cn"])
        self.assertEqual(top_rec["severity"], "critical")

    def test_preflight_wsl_database_match(self):
        """Verify preflight flags WSL NTFS sqlite bottleneck."""
        res = preflight_check(
            intent="sqlite_batch_update on large database",
            commands=["sqlite3", "/mnt/d/data.db"],
            environments=["wsl2", "ntfs"],
            risks=["fsync_latency"],
        )
        self.assertEqual(res["status"], "warning")
        self.assertIn(res["risk_level"], ["high", "critical"])
        matched_ids = [r["id"] for r in res["recommendations"]]
        self.assertIn("wsl-ntfs-sqlite-update-100x-slower", matched_ids)

    def test_preflight_clean_query(self):
        """Verify preflight returns clean for unrelated safe intents."""
        res = preflight_check(
            intent="print simple hello world python script",
            commands=["echo hello"],
            environments=["bare_metal"],
        )
        self.assertEqual(res["status"], "clean")
        self.assertEqual(res["risk_level"], "none")
        self.assertFalse(res["requires_confirmation"])
        self.assertEqual(res["matched_count"], 0)


if __name__ == "__main__":
    unittest.main()
