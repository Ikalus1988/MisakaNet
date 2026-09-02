#!/usr/bin/env python3
"""Tests for scripts/intake_pipeline.py (PRD ③) — parse/classify/draft/precheck."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import intake_pipeline as ip


class TestParseIntake(unittest.TestCase):
    def test_parse_normalizes_fields(self):
        raw = {"kind": "missing_lesson", "problem": "pip timeout", "source": "mcp", "source_id": "s1"}
        out = ip.parse_intake(raw)
        self.assertEqual(out["kind"], "missing_lesson")
        self.assertEqual(out["source_id"], "s1")
        self.assertEqual(out["title"], "")

    def test_parse_defaults_kind_and_source_id(self):
        out = ip.parse_intake({"problem": "x"})
        self.assertEqual(out["kind"], "missing_lesson")
        self.assertEqual(out["source"], "mcp")
        self.assertTrue(out["source_id"].startswith("mcp-"))

    def test_parse_rejects_unknown_kind(self):
        out = ip.parse_intake({"kind": "bogus", "problem": "x"})
        self.assertEqual(out["kind"], "missing_lesson")


class TestClassify(unittest.TestCase):
    def test_python_domain_hint(self):
        intake = ip.parse_intake({"problem": "pip install fails with traceback", "kind": "missing_lesson"})
        cls = ip.classify(intake)
        self.assertEqual(cls["domain"], "python")

    def test_explicit_domain_wins(self):
        intake = ip.parse_intake({"problem": "python error", "domain": "devops", "kind": "missing_lesson"})
        cls = ip.classify(intake)
        self.assertEqual(cls["domain"], "devops")

    def test_question_type(self):
        intake = ip.parse_intake({"problem": "how to fix?", "kind": "question"})
        cls = ip.classify(intake)
        self.assertEqual(cls["type"], "question")


class TestGenerateDraft(unittest.TestCase):
    def test_draft_has_frontmatter_and_sections(self):
        intake = ip.parse_intake({"kind": "missing_lesson", "problem": "service crashes on start",
                                  "error": "Segfault", "fix": "increase stack size",
                                  "verification": "restart ok", "source": "mcp", "source_id": "d1"})
        cls = ip.classify(intake)
        draft = ip.generate_draft(intake, cls)
        self.assertTrue(draft["content_md"].startswith("---"))
        self.assertIn("## Problem", draft["content_md"])
        self.assertIn("## Solution", draft["content_md"])
        self.assertIn("## Verification", draft["content_md"])
        self.assertTrue(draft["slug"])

    def test_draft_marks_missing_solution(self):
        intake = ip.parse_intake({"kind": "missing_lesson", "problem": "something broke", "source": "mcp"})
        cls = ip.classify(intake)
        draft = ip.generate_draft(intake, cls)
        self.assertIn("pending review", draft["content_md"])


class TestPrecheck(unittest.TestCase):
    def test_short_problem_flagged(self):
        intake = ip.parse_intake({"kind": "missing_lesson", "problem": "short", "source": "mcp"})
        cls = ip.classify(intake)
        draft = ip.generate_draft(intake, cls)
        pre = ip.precheck(intake, draft)
        self.assertTrue(any("PROBLEM_TOO_SHORT" in i for i in pre["issues"]))
        self.assertLess(pre["score"], 100)

    def test_secret_pattern_flagged(self):
        intake = ip.parse_intake({"kind": "missing_lesson",
                                  "problem": "token ghp_abcdefghijklmnopqrstuvwxyz leaked",
                                  "source": "mcp"})
        cls = ip.classify(intake)
        draft = ip.generate_draft(intake, cls)
        pre = ip.precheck(intake, draft)
        self.assertTrue(any("SECRET_PATTERN" in i for i in pre["issues"]))

    def test_complete_intake_passes(self):
        intake = ip.parse_intake({"kind": "missing_lesson", "problem": "database connection pool exhausted",
                                  "fix": "increase pool size", "verification": "load test passes",
                                  "source": "mcp"})
        cls = ip.classify(intake)
        draft = ip.generate_draft(intake, cls)
        pre = ip.precheck(intake, draft)
        self.assertTrue(pre["pass"])


class TestRun(unittest.TestCase):
    def test_dry_run_returns_preview_without_persisting(self):
        result = ip.run({"kind": "question", "problem": "how does sync work?", "source": "mcp"}, dry_run=True)
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["kind"], "question")
        self.assertIn("draft_preview", result)


if __name__ == "__main__":
    unittest.main()
