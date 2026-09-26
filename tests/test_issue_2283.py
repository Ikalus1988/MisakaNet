#!/usr/bin/env python3
"""Regression test suite for Issue #2283: Unhandled boundary failure / logic exception in check_provenance.py."""
from __future__ import annotations

import os
import pathlib
import shutil
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import check_provenance as cp  # noqa: E402


class TestCheckProvenanceIssue2283(unittest.TestCase):
    """Regression and boundary tests for scripts/check_provenance.py."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_issue_2283_")
        self.temp_path = pathlib.Path(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_01_normal_flow(self):
        """Test regular frontmatter parsing, resolution, and evaluation."""
        lesson_file = self.temp_path / "valid_lesson.md"
        lesson_file.write_text(
            "---\n"
            "title: Normal Lesson\n"
            "domain: devops\n"
            "evidence_level: E2\n"
            "provenance:\n"
            '  source: "https://github.com/example/repo/issues/100"\n'
            "---\n"
            "## Problem\nSome issue\n",
            encoding="utf-8",
        )

        def mock_fetcher(url, token=""):
            return 200, ""

        rows = cp.scan([lesson_file], fetcher=mock_fetcher)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "ok")
        self.assertEqual(rows[0]["evidence_level"], "E2")

        failures, advisories = cp.evaluate(
            rows,
            {"known_dead": [], "exempt_urls": []},
            strict_new={cp.rel_to_repo(lesson_file)},
        )
        self.assertEqual(failures, [])
        self.assertEqual(advisories, [])

    def test_02_boundary_handling(self):
        """Test defensive behavior on boundary, None, empty, and malformed inputs."""
        # _host_of edge cases
        self.assertEqual(cp._host_of(None), "")
        self.assertEqual(cp._host_of(""), "")
        self.assertEqual(cp._host_of(123), "")
        self.assertEqual(cp._host_of("https://[2001:db8::1]:8080"), "2001:db8::1")
        self.assertEqual(cp._host_of("https://[unclosed-bracket"), "unclosed-bracket")
        self.assertEqual(cp._host_of("https://["), "")

        # is_non_public_host edge cases
        self.assertTrue(cp.is_non_public_host(None))
        self.assertTrue(cp.is_non_public_host(""))
        self.assertTrue(cp.is_non_public_host(None))
        self.assertTrue(cp.is_non_public_host("localhost"))
        self.assertFalse(cp.is_non_public_host("github.com"))

        # resolves_non_public edge cases
        self.assertFalse(cp.resolves_non_public(None))
        self.assertFalse(cp.resolves_non_public(""))
        self.assertFalse(cp.resolves_non_public("   "))

        # classify edge cases
        self.assertEqual(cp.classify(None), "exempt")
        self.assertEqual(cp.classify(""), "exempt")
        self.assertEqual(cp.classify("https://example.com/test"), "exempt")
        self.assertEqual(cp.classify("https://github.com/<owner>/repo"), "placeholder")
        self.assertEqual(cp.classify("https://github.com/torvalds/linux"), "check")

        # github_api_url edge cases
        self.assertIsNone(cp.github_api_url(None))
        self.assertIsNone(cp.github_api_url(""))
        self.assertIsNone(cp.github_api_url("https://notgithub.com/foo/bar"))
        self.assertEqual(
            cp.github_api_url("https://github.com/org/repo/issues/42"),
            "https://api.github.com/repos/org/repo/issues/42",
        )

        # resolve edge cases
        status, detail = cp.resolve(None)
        self.assertEqual(status, "exempt")
        status, detail = cp.resolve("")
        self.assertEqual(status, "exempt")

        # frontmatter / citations / evidence_level edge cases
        self.assertEqual(cp.frontmatter(None), "")
        self.assertEqual(cp.frontmatter(""), "")
        self.assertEqual(cp.frontmatter("no frontmatter"), "")
        self.assertEqual(cp.citations(None), [])
        self.assertEqual(cp.citations(""), [])
        self.assertEqual(cp.evidence_level(None), "")
        self.assertEqual(cp.evidence_level(""), "")

        # scan edge cases: directory and non-existent path must not raise IsADirectoryError or FileNotFoundError
        non_existent = self.temp_path / "does_not_exist.md"
        rows_empty = cp.scan([self.temp_path, non_existent, None])
        self.assertEqual(rows_empty, [])

        # lesson_files edge cases: directory expansion and missing files
        files = cp.lesson_files([str(self.temp_path), str(non_existent), ""])
        self.assertIn(non_existent, files)

    def test_03_contract_integrity(self):
        """Test evaluate contract integrity with None/empty parameters."""
        # Contract: evaluate returns tuple[list[str], list[str]]
        failures, advisories = cp.evaluate(None, None, None)
        self.assertIsInstance(failures, list)
        self.assertIsInstance(advisories, list)
        self.assertEqual(failures, [])
        self.assertEqual(advisories, [])

        # Corrupted baseline schema
        corrupt_baseline = {
            "known_dead": [None, "invalid_entry", {"not_url": "foo"}],
            "exempt_urls": None,
        }
        failures, advisories = cp.evaluate([], corrupt_baseline, None)
        self.assertEqual(failures, [])
        self.assertEqual(advisories, [])

        # Corrupted row elements
        bad_rows = [None, {}, {"lesson": "foo.md"}, {"status": "ok"}]
        failures, advisories = cp.evaluate(bad_rows, None, None)
        self.assertEqual(failures, [])
        self.assertEqual(advisories, [])

    def test_04_integration_consistency(self):
        """Test integrated scan + evaluate pipeline across mixed citations."""
        lesson_file = self.temp_path / "mixed_lesson.md"
        lesson_file.write_text(
            "---\n"
            "title: Mixed Citations\n"
            "domain: devops\n"
            "evidence_level: E3\n"
            "provenance:\n"
            '  source: "https://github.com/<owner>/<repo>/issues/1"\n'
            "evidence_refs:\n"
            '  - "http://127.0.0.1:8080/health"\n'
            '  - "https://github.com/dead/link/issues/999"\n'
            "---\n"
            "## Problem\nMixed citations\n",
            encoding="utf-8",
        )

        def mock_fetcher(url, token=""):
            if "dead" in url:
                return 404, "Not Found"
            return 200, ""

        rows = cp.scan([lesson_file], fetcher=mock_fetcher)
        self.assertEqual(len(rows), 3)

        statuses = {r["url"]: r["status"] for r in rows}
        self.assertEqual(statuses["https://github.com/<owner>/<repo>/issues/1"], "placeholder")
        self.assertEqual(statuses["http://127.0.0.1:8080/health"], "exempt")
        self.assertEqual(statuses["https://github.com/dead/link/issues/999"], "dead")

        failures, advisories = cp.evaluate(
            rows,
            {"known_dead": [], "exempt_urls": []},
            strict_new={cp.rel_to_repo(lesson_file)},
        )
        self.assertEqual(len(failures), 2)  # 1 placeholder + 1 dead
        self.assertTrue(any("placeholder" in f for f in failures))
        self.assertTrue(any("does not resolve" in f for f in failures))


if __name__ == "__main__":
    unittest.main()
