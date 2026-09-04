#!/usr/bin/env python3
"""Unit tests for scripts/sync_answered_questions.py (PRD ⑤ / Issue #1464)."""
import json
import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import sync_answered_questions as saq


class TestFnv1aParity(unittest.TestCase):
    """Verify FNV-1a hash matches JS worker hashString."""

    def test_known_vectors(self):
        # Empty string FNV-1a basis
        self.assertEqual(saq.fnv1a_hex(""), "811c9dc5")
        # Standard test strings
        self.assertEqual(saq.fnv1a_hex("a"), "e40c292c")
        self.assertEqual(saq.fnv1a_hex("hello"), "4f9f2cab")

    def test_composite_dedup_source(self):
        # Example dedupSource: kind:problem:error
        s = "question:How to configure MCP auth?:None"
        h = saq.fnv1a_hex(s)
        self.assertEqual(len(h), 8)
        self.assertTrue(all(c in "0123456789abcdef" for c in h))


class TestParseKindAndProblem(unittest.TestCase):
    """Test parsing of kind, problem, and error from issue body."""

    def test_structured_body(self):
        body = """**Kind:** Question
**Source:** mcp

## Problem
How do I configure MCP server authentication in production?

## Error
None

## Verification
Checked logs and docs.
"""
        kind, problem, error = saq.parse_kind_and_problem(body)
        self.assertEqual(kind, "question")
        self.assertEqual(problem, "How do I configure MCP server authentication in production?")
        self.assertEqual(error, "None")

    def test_unstructured_body_fallback(self):
        body = """**Kind:** question
<details><summary>Details</summary>Internal trace</details>
Can someone explain the D1 schema migration steps?
"""
        kind, problem, error = saq.parse_kind_and_problem(body)
        self.assertEqual(kind, "question")
        self.assertIn("Can someone explain the D1 schema migration steps?", problem)
        self.assertEqual(error, "")

    def test_missing_kind(self):
        body = "Just a general comment without frontmatter headers"
        kind, problem, error = saq.parse_kind_and_problem(body)
        self.assertEqual(kind, "")
        self.assertEqual(problem, "Just a general comment without frontmatter headers")
        self.assertEqual(error, "")


class TestExtractAnswer(unittest.TestCase):
    """Test extraction of maintainer answer comments and filtering of automated bots."""

    def test_explicit_answer_marker(self):
        comments = [
            {"id": 101, "body": "<!-- misakanet-intake-triage -->\nTriage bot comment", "user": {"login": "misaka-bot"}},
            {"id": 102, "body": "## ✅ Answered\nYou need to set the MCP_API_KEY environment variable.", "user": {"login": "maintainer"}, "created_at": "2026-09-03T12:00:00Z"}
        ]
        ans, created_at, cid = saq.extract_answer(comments)
        self.assertIn("You need to set the MCP_API_KEY", ans)
        self.assertEqual(created_at, "2026-09-03T12:00:00Z")
        self.assertEqual(cid, 102)

    def test_fallback_long_human_comment(self):
        comments = [
            {"id": 201, "body": "Short note", "user": {"login": "random"}, "created_at": "2026-09-03T10:00:00Z"},
            {"id": 202, "body": "Here is the detailed solution to resolve your issue with the cloudflare worker database connection. Make sure to bind D1 in wrangler.toml under d1_databases.", "user": {"login": "contributor"}, "created_at": "2026-09-03T11:00:00Z"}
        ]
        ans, created_at, cid = saq.extract_answer(comments)
        self.assertIn("Here is the detailed solution", ans)
        self.assertEqual(cid, 202)

    def test_ignore_automated_and_bot_comments(self):
        comments = [
            {"id": 301, "body": "<!-- misakanet-duplicate -->\nPossible duplicate of #100", "user": {"login": "bot"}},
            {"id": 302, "body": "Short non-answer", "user": {"login": "bot[bot]"}},
        ]
        ans, created_at, cid = saq.extract_answer(comments)
        self.assertIsNone(ans)
        self.assertIsNone(created_at)
        self.assertIsNone(cid)


class TestD1SqlUpsert(unittest.TestCase):
    """Test pending and answered upsert logic against in-memory SQLite (mock D1)."""

    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("""
            CREATE TABLE questions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              issue_number INTEGER UNIQUE NOT NULL,
              dedup_hash TEXT,
              problem TEXT NOT NULL,
              source TEXT DEFAULT mcp,
              status TEXT DEFAULT pending,
              answer TEXT,
              answer_comment_id INTEGER,
              issue_url TEXT,
              created TEXT DEFAULT CURRENT_TIMESTAMP,
              answered_at TEXT,
              updated TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def fake_d1_query(self, sql: str, params: list | None = None) -> dict:
        cur = self.conn.cursor()
        import re
        formatted_sql = re.sub(r"\?\d+", "?", sql)
        cur.execute(formatted_sql, params or [])
        self.conn.commit()
        if sql.strip().upper().startswith("SELECT"):
            columns = [col[0] for col in cur.description] if cur.description else []
            rows = [dict(zip(columns, r)) for r in cur.fetchall()]
            return {"result": [{"results": rows}]}
        return {"result": [{"results": []}]}

    def test_upsert_pending_new_and_existing(self):
        with patch.object(saq, "d1_query", side_effect=self.fake_d1_query):
            issue = {
                "number": 1390,
                "html_url": "https://github.com/Ikalus1988/MisakaNet/issues/1390",
                "body": "**Kind:** question\n## Problem\nHow to cache responses?"
            }
            # First insertion
            res1 = saq.upsert_pending(issue)
            self.assertTrue(res1)
            self.assertTrue(saq.row_exists(1390))

            cur = self.conn.cursor()
            cur.execute("SELECT status, dedup_hash, problem FROM questions WHERE issue_number = 1390")
            row = cur.fetchone()
            self.assertEqual(row[0], "pending")
            self.assertEqual(row[2], "How to cache responses?")

            # Second upsert refresh
            res2 = saq.upsert_pending(issue)
            self.assertFalse(res2)

    def test_upsert_answered(self):
        with patch.object(saq, "d1_query", side_effect=self.fake_d1_query):
            with patch.object(saq, "fetch_issue_comments", return_value=[
                {"id": 999, "body": "## ✅ Answered\nUse Cache-Control headers with KV caching.", "created_at": "2026-09-03T15:00:00Z"}
            ]):
                issue = {
                    "number": 1395,
                    "html_url": "https://github.com/Ikalus1988/MisakaNet/issues/1395",
                    "body": "**Kind:** question\n## Problem\nHow to cache responses?",
                    "closed_at": "2026-09-03T15:10:00Z"
                }
                # Insert directly as answered
                ok = saq.upsert_answered(issue)
                self.assertTrue(ok)

                cur = self.conn.cursor()
                cur.execute("SELECT status, answer, answer_comment_id FROM questions WHERE issue_number = 1395")
                row = cur.fetchone()
                self.assertEqual(row[0], "answered")
                self.assertIn("Use Cache-Control headers", row[1])
                self.assertEqual(row[2], 999)


if __name__ == "__main__":
    unittest.main()
