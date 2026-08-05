#!/usr/bin/env python3
"""Tests for scripts/quality_scorer.py -- 100-point rubric implementation."""

import json
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys_path_backup = None

import sys

sys.path.insert(0, str(REPO))

from scripts.quality_scorer import (
    extract_frontmatter,
    get_body,
    find_sections,
    word_count,
    score_metadata,
    score_structure,
    score_content,
    score_dedup,
    score_source_trust,
    score_lesson,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class TestExtractFrontmatter(unittest.TestCase):
    def test_json_frontmatter(self):
        content = '---\n{"title": "Test", "domain": "ops"}\n---\nBody'
        fm, err = extract_frontmatter(content)
        self.assertIsNone(err)
        self.assertEqual(fm["title"], "Test")

    def test_no_frontmatter(self):
        fm, err = extract_frontmatter("No frontmatter here")
        self.assertIsNone(fm)
        self.assertIn("No frontmatter", err)

    def test_invalid_json(self):
        content = '---\nnot json\n---\nBody'
        fm, err = extract_frontmatter(content)
        self.assertTrue(fm is not None or err is not None)


class TestScoreMetadata(unittest.TestCase):
    def test_good_metadata(self):
        fm = {
            "title": "Fix database locked error on concurrent writes",
            "domain": "devops",
            "tags": ["sqlite", "database", "locking"],
            "source": "https://github.com/example/repo",
            "created": "2026-07-01",
            "confidence": "0.85",
        }
        pts, notes = score_metadata(fm, "")
        self.assertEqual(pts, 20)
        self.assertEqual(notes, [])

    def test_no_frontmatter(self):
        pts, notes = score_metadata(None, "")
        self.assertEqual(pts, 0)

    def test_short_title(self):
        fm = {
            "title": "Fix",
            "domain": "ops",
            "tags": ["a", "b", "c"],
            "source": "x",
            "created": "2026-01-01",
            "confidence": "0.5",
        }
        pts, notes = score_metadata(fm, "")
        self.assertLess(pts, 20)
        self.assertTrue(any("Title" in n for n in notes))

    def test_missing_tags(self):
        fm = {
            "title": "A long enough title here",
            "domain": "ops",
            "source": "x",
            "created": "2026-01-01",
            "confidence": "0.5",
        }
        pts, notes = score_metadata(fm, "")
        self.assertTrue(any("Tags" in n for n in notes))


class TestScoreStructure(unittest.TestCase):
    def test_all_sections_present(self):
        body = (
            "## Problem\n\nX\n\n## Root Cause\n\nY\n\n"
            "## Solution\n\nZ\n\n## Verification\n\nV\n\n## Notes\n\nN"
        )
        pts, notes = score_structure(body)
        self.assertEqual(pts, 25)
        self.assertEqual(notes, [])

    def test_missing_root_cause(self):
        body = "## Problem\n\nX\n\n## Solution\n\nZ\n\n## Verification\n\nV"
        pts, notes = score_structure(body)
        self.assertLess(pts, 25)
        self.assertTrue(any("Root Cause" in n for n in notes))

    def test_out_of_order(self):
        body = (
            "## Solution\n\nZ\n\n## Problem\n\nX\n\n## Root Cause\n\nY\n\n"
            "## Verification\n\nV\n\n## Notes\n\nN"
        )
        pts, notes = score_structure(body)
        self.assertTrue(any("order" in n.lower() for n in notes))


class TestScoreContent(unittest.TestCase):
    def test_rich_content(self):
        content = load_fixture("good_lesson.md")
        body = get_body(content)
        pts, notes = score_content(body)
        self.assertGreaterEqual(pts, 25)

    def test_no_code_blocks(self):
        body = (
            "## Problem\n\nSome text without any code.\n\n"
            "## Solution\n\nDo the thing step by step.\n\n"
            "## Verification\n\nCheck it works."
        )
        pts, notes = score_content(body)
        self.assertTrue(any("code block" in n.lower() for n in notes))

    def test_stub_content(self):
        body = "## Problem\n\nShort.\n\n## Solution\n\nFix it."
        pts, notes = score_content(body)
        self.assertLess(pts, 15)


class TestScoreDedup(unittest.TestCase):
    def test_clean_content(self):
        content = (
            "## Problem\n\nGeneric lesson about CI pipelines.\n\n"
            "## Solution\n\nUse GitHub Actions."
        )
        pts, notes = score_dedup(content)
        self.assertEqual(pts, 10)

    def test_org_sensitive(self):
        pts, notes = score_dedup("This uses Xiaomi mify gateway internally")
        self.assertLess(pts, 10)
        self.assertTrue(any("org-sensitive" in n.lower() for n in notes))

    def test_hardcoded_paths(self):
        pts, notes = score_dedup("Config is at /Users/eric/.config/app.json")
        self.assertTrue(any("hardcoded" in n.lower() for n in notes))

    def test_self_similarity_excluded(self):
        all_docs = [("test-lesson.md", {"fix", "database", "locked"})]
        pts, notes = score_dedup(
            "fix database locked error",
            all_docs,
            current_file="lessons/contrib/test-lesson.md",
        )
        self.assertEqual(pts, 10)


class TestScoreSourceTrust(unittest.TestCase):
    def test_github_source(self):
        fm = {"source": "https://github.com/org/repo/issues/1"}
        pts, notes = score_source_trust(fm, "resolved in PR #2")
        self.assertGreaterEqual(pts, 6)

    def test_no_source(self):
        fm = {"source": ""}
        pts, notes = score_source_trust(fm, "")
        self.assertLess(pts, 5)

    def test_verified_expert(self):
        fm = {
            "source": "https://github.com/org/repo",
            "verified_date": "2026-07-01",
            "domain_expert": "maintainer",
        }
        pts, notes = score_source_trust(fm, "verified and merged")
        self.assertEqual(pts, 10)


class TestScoreLessonIntegration(unittest.TestCase):
    def _write_fixture(self, name: str) -> Path:
        content = load_fixture(name)
        tmp = tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode="w")
        tmp.write(content)
        tmp.close()
        return Path(tmp.name)

    def test_good_lesson_passes(self):
        path = self._write_fixture("good_lesson.md")
        try:
            r = score_lesson(path)
            self.assertGreaterEqual(r["score"], 75)
            self.assertTrue(r["pass"])
            self.assertIn(r["grade"], ("A", "B"))
        finally:
            path.unlink()

    def test_bad_lesson_fails(self):
        path = self._write_fixture("bad_lesson.md")
        try:
            r = score_lesson(path)
            self.assertLess(r["score"], 60)
            self.assertFalse(r["pass"])
        finally:
            path.unlink()

    def test_no_frontmatter_scores_zero_metadata(self):
        path = self._write_fixture("no_frontmatter.md")
        try:
            r = score_lesson(path)
            self.assertEqual(r["breakdown"]["metadata"]["score"], 0)
        finally:
            path.unlink()

    def test_placeholder_detected(self):
        path = self._write_fixture("placeholder_lesson.md")
        try:
            r = score_lesson(path)
            content_notes = r["breakdown"]["content"]["notes"]
            self.assertTrue(
                any("TODO" in n or "placeholder" in n.lower() for n in content_notes)
            )
        finally:
            path.unlink()

    def test_org_sensitive_flagged(self):
        path = self._write_fixture("org_sensitive_lesson.md")
        try:
            r = score_lesson(path)
            dedup_notes = r["breakdown"]["dedup"]["notes"]
            self.assertTrue(any("org-sensitive" in n.lower() for n in dedup_notes))
        finally:
            path.unlink()

    def test_json_output_structure(self):
        path = self._write_fixture("good_lesson.md")
        try:
            r = score_lesson(path)
            self.assertIn("file", r)
            self.assertIn("score", r)
            self.assertIn("grade", r)
            self.assertIn("pass", r)
            self.assertIn("breakdown", r)
            for dim in ("metadata", "structure", "content", "dedup", "trust"):
                self.assertIn(dim, r["breakdown"])
                self.assertIn("score", r["breakdown"][dim])
                self.assertIn("max", r["breakdown"][dim])
                self.assertIn("notes", r["breakdown"][dim])
        finally:
            path.unlink()


if __name__ == "__main__":
    unittest.main()
