#!/usr/bin/env python3
"""Tests for scripts/quality_scorer.py — 100-point rubric implementation."""

import json
import tempfile
import unittest
from pathlib import Path

# Add repo to path
import sys
REPO = Path(__file__).resolve().parent.parent
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


GOOD_LESSON = """---
{
  "title": "Fix database locked error on concurrent writes",
  "domain": "devops",
  "tags": ["sqlite", "database", "locking", "concurrency"],
  "status": "published",
  "confidence": "0.85",
  "created": "2026-07-01",
  "updated": "2026-07-10",
  "source": "https://github.com/example/repo/issues/42",
  "language": "en"
}
---

## Problem

When multiple processes write to the same SQLite database simultaneously,
you get `database is locked` errors. This happens in CI pipelines where
parallel jobs share a state file.

Specific error message:
```
sqlite3.OperationalError: database is locked
```

## Root Cause

SQLite uses file-level locking. When one writer holds a lock, all other
writers must wait. If they exceed the timeout (default 5s), they fail.

The issue is that WAL mode was not enabled, and busy_timeout was too low.

## Solution

1. Enable WAL mode for concurrent reads:
```sql
PRAGMA journal_mode=WAL;
```

2. Set busy timeout to 30 seconds:
```sql
PRAGMA busy_timeout=30000;
```

3. Add retry logic in application code:
```python
import time

def db_write_with_retry(conn, query, max_retries=3):
    for attempt in range(max_retries):
        try:
            conn.execute(query)
            conn.commit()
            return True
        except sqlite3.OperationalError as e:
            if "locked" in str(e) and attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise
    return False
```

## Verification

After applying WAL + busy_timeout:

```bash
# Run parallel writes
for i in $(seq 1 10); do
  python3 write_to_db.py &
done
wait
# Expected: no "database is locked" errors
```

Confirm WAL mode is active:
```sql
PRAGMA journal_mode;
-- Expected: wal
```

## Notes

- WAL mode only works on local filesystems, not NFS
- For distributed locking, consider PostgreSQL or a dedicated lock service
- See also: [SQLite WAL documentation](https://www.sqlite.org/wal.html)
"""

BAD_LESSON = """---
{
  "title": "Fix",
  "domain": "",
  "tags": ["bug"],
  "status": "published"
}
---

## Problem

Something broke.

## Fix

Run the command.
"""

NO_FRONTMATTER = """## Problem

No frontmatter at all.

## Solution

Just do stuff.

## Notes

Some notes.
"""

PLACEHOLDER_LESSON = """---
{
  "title": "Work in progress lesson about X",
  "domain": "devops",
  "tags": ["wip", "placeholder", "draft"],
  "status": "draft",
  "confidence": "0.3",
  "created": "2026-07-01",
  "source": "https://github.com/example/repo"
}
---

## Problem

TODO: describe the problem here.

## Root Cause

FIXME: explain root cause.

## Solution

Coming soon.

## Verification

To be written.

## Notes

Placeholder content.
"""

ORG_SENSITIVE_LESSON = """---
{
  "title": "Internal Xiaomi API rate limiting workaround",
  "domain": "ops",
  "tags": ["xiaomi", "api", "rate-limit"],
  "status": "published",
  "confidence": "0.7",
  "created": "2026-07-01",
  "source": "https://mi.feishu.cn/docs/xxx"
}
---

## Problem

The Xiaomi internal API at mi.feishu.cn returns 429.

## Root Cause

Internal rate limit is 100 req/min for the mify gateway.

## Solution

Add exponential backoff. Use the internal Xiaomi SDK.

## Verification

Tested on internal Xiaomi staging environment.

## Notes

This is specific to Xiaomi's internal infrastructure.
"""


class TestExtractFrontmatter(unittest.TestCase):
    """Test frontmatter extraction."""

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
        # YAML-like fallback should parse "not json" as a key
        fm, err = extract_frontmatter(content)
        # Either parsed as YAML or returned error
        self.assertTrue(fm is not None or err is not None)


class TestScoreMetadata(unittest.TestCase):
    """Test metadata scoring (max 20)."""

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
        fm = {"title": "Fix", "domain": "ops", "tags": ["a", "b", "c"],
              "source": "x", "created": "2026-01-01", "confidence": "0.5"}
        pts, notes = score_metadata(fm, "")
        self.assertLess(pts, 20)
        self.assertTrue(any("Title" in n for n in notes))

    def test_missing_tags(self):
        fm = {"title": "A long enough title here", "domain": "ops",
              "source": "x", "created": "2026-01-01", "confidence": "0.5"}
        pts, notes = score_metadata(fm, "")
        self.assertTrue(any("Tags" in n for n in notes))


class TestScoreStructure(unittest.TestCase):
    """Test structure scoring (max 25)."""

    def test_all_sections_present(self):
        body = """## Problem\n\nX\n\n## Root Cause\n\nY\n\n## Solution\n\nZ\n\n## Verification\n\nV\n\n## Notes\n\nN"""
        pts, notes = score_structure(body)
        self.assertEqual(pts, 25)
        self.assertEqual(notes, [])

    def test_missing_root_cause(self):
        body = """## Problem\n\nX\n\n## Solution\n\nZ\n\n## Verification\n\nV"""
        pts, notes = score_structure(body)
        self.assertLess(pts, 25)
        self.assertTrue(any("Root Cause" in n for n in notes))

    def test_out_of_order(self):
        body = """## Solution\n\nZ\n\n## Problem\n\nX\n\n## Root Cause\n\nY\n\n## Verification\n\nV\n\n## Notes\n\nN"""
        pts, notes = score_structure(body)
        self.assertTrue(any("order" in n.lower() for n in notes))


class TestScoreContent(unittest.TestCase):
    """Test content quality scoring (max 35)."""

    def test_rich_content(self):
        body = GOOD_LESSON.split("---\n")[2]  # Get body after frontmatter
        pts, notes = score_content(body)
        self.assertGreaterEqual(pts, 25)

    def test_no_code_blocks(self):
        body = "## Problem\n\nSome text without any code.\n\n## Solution\n\nDo the thing step by step.\n\n## Verification\n\nCheck it works."
        pts, notes = score_content(body)
        self.assertTrue(any("code block" in n.lower() for n in notes))

    def test_stub_content(self):
        body = "## Problem\n\nShort.\n\n## Solution\n\nFix it."
        pts, notes = score_content(body)
        self.assertLess(pts, 15)


class TestScoreDedup(unittest.TestCase):
    """Test dedup scoring (max 10)."""

    def test_clean_content(self):
        content = "## Problem\n\nGeneric lesson about CI pipelines.\n\n## Solution\n\nUse GitHub Actions."
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
        """Should not flag a file as duplicate of itself."""
        all_docs = [("test-lesson.md", {"fix", "database", "locked"})]
        pts, notes = score_dedup(
            "fix database locked error",
            all_docs,
            current_file="lessons/contrib/test-lesson.md",
        )
        # Should get full 5 pts since the only doc is itself
        self.assertEqual(pts, 10)  # 3 (no org) + 2 (no paths) + 5 (no dup)


class TestScoreSourceTrust(unittest.TestCase):
    """Test source trust scoring (max 10)."""

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
    """Test full lesson scoring integration."""

    def _write_temp(self, content: str) -> Path:
        tmp = tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode="w")
        tmp.write(content)
        tmp.close()
        return Path(tmp.name)

    def test_good_lesson_passes(self):
        path = self._write_temp(GOOD_LESSON)
        try:
            r = score_lesson(path)
            self.assertGreaterEqual(r["score"], 75)
            self.assertTrue(r["pass"])
            self.assertIn(r["grade"], ("A", "B"))
        finally:
            path.unlink()

    def test_bad_lesson_fails(self):
        path = self._write_temp(BAD_LESSON)
        try:
            r = score_lesson(path)
            self.assertLess(r["score"], 60)
            self.assertFalse(r["pass"])
        finally:
            path.unlink()

    def test_no_frontmatter_scores_zero_metadata(self):
        path = self._write_temp(NO_FRONTMATTER)
        try:
            r = score_lesson(path)
            self.assertEqual(r["breakdown"]["metadata"]["score"], 0)
        finally:
            path.unlink()

    def test_placeholder_detected(self):
        path = self._write_temp(PLACEHOLDER_LESSON)
        try:
            r = score_lesson(path)
            # Should have notes about placeholders
            content_notes = r["breakdown"]["content"]["notes"]
            self.assertTrue(any("TODO" in n or "placeholder" in n.lower() for n in content_notes))
        finally:
            path.unlink()

    def test_org_sensitive_flagged(self):
        path = self._write_temp(ORG_SENSITIVE_LESSON)
        try:
            r = score_lesson(path)
            dedup_notes = r["breakdown"]["dedup"]["notes"]
            self.assertTrue(any("org-sensitive" in n.lower() for n in dedup_notes))
        finally:
            path.unlink()

    def test_json_output_structure(self):
        """Verify output has all expected fields."""
        path = self._write_temp(GOOD_LESSON)
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
