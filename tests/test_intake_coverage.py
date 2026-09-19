"""Tests for intake_coverage.py — normalization and query extraction."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts.intake_coverage import (
    classify_results,
    extract_queries,
    normalize_title,
    strip_boilerplate,
)


class TestStripBoilerplate:
    def test_removes_pipeline_metadata(self):
        body = """**Kind:** new_lesson_candidate
**Source:** dsh
**Dedup:** `dfb89d73-7c1`

## Problem
Docker build fails.

---
_Submitted via remote MCP (dsh). No account required._"""
        result = strip_boilerplate(body)
        assert "Kind" not in result
        assert "Submitted via" not in result
        assert "Docker build fails" in result

    def test_removes_opire_block(self):
        body = """## Problem
Some issue here.

<details><summary>This repo is using Opire</summary>
blah blah
</details>"""
        result = strip_boilerplate(body)
        assert "Opire" not in result
        assert "Some issue here" in result

    def test_empty_body(self):
        assert strip_boilerplate("") == ""


class TestNormalizeTitle:
    def test_removes_intake_prefix(self):
        assert "Docker build fails" in normalize_title("[Intake] Docker build fails")

    def test_removes_question_prefix(self):
        assert "How to fix" in normalize_title("[Question] How to fix")

    def test_removes_markdown_formatting(self):
        result = normalize_title("**bold** and _italic_ and `code`")
        assert "*" not in result
        assert "_" not in result
        assert "`" not in result

    def test_removes_parenthetical(self):
        result = normalize_title("Docker build fails (exit code 137)")
        assert "(" not in result
        assert "Docker build fails" in result

    def test_collapses_whitespace(self):
        result = normalize_title("Docker  build   fails")
        assert "  " not in result


class TestExtractQueries:
    def test_long_title_normalized(self):
        """#1460-like: long title should produce meaningful short query."""
        title = "Docker build fails with exit code 137 when using multi-stage builds in CI pipeline"
        queries = extract_queries(title)
        assert len(queries) >= 1
        # Should contain error code
        assert any("137" in q for q in queries)
        # Should contain docker
        assert any("docker" in q.lower() for q in queries)

    def test_bilingual_title(self):
        """Portuguese/English mix should still extract technical terms."""
        title = "In roleplay chat, third-person narrative or pronoun 'Ele' was interpreted as speaker"
        queries = extract_queries(title)
        assert len(queries) >= 1

    def test_removes_stop_words(self):
        title = "The Docker build is failing with an error in the pipeline"
        queries = extract_queries(title)
        for q in queries:
            words = q.lower().split()
            # No stop words should be the only words
            assert len(words) >= 2

    def test_generates_multiple_queries(self):
        title = "Docker build fails with exit code 137 when using multi-stage builds"
        body = "## Problem\nDocker multi-stage build fails.\n\n## Error\nexit code 137"
        queries = extract_queries(title, body)
        assert len(queries) >= 2

    def test_deduplicates_queries(self):
        title = "Docker Docker Docker build fails"
        queries = extract_queries(title)
        assert len(queries) == len(set(queries))


class TestClassifyResults:
    def test_lesson_above_threshold(self):
        results = [
            {"title": "Docker exit code 137", "score": 10.0, "status": "published", "tags": ["docker"]},
        ]
        assert classify_results(results, 5.0) == "lesson-covered"

    def test_only_faq(self):
        results = [
            {"title": "FAQ: Docker", "score": 8.0, "status": "faq", "tags": ["faq"]},
        ]
        assert classify_results(results, 5.0) == "faq-only"

    def test_no_coverage(self):
        results = []
        assert classify_results(results, 5.0) == "no-coverage"

    def test_below_threshold_ignored(self):
        results = [
            {"title": "Something", "score": 2.0, "status": "published", "tags": []},
        ]
        assert classify_results(results, 5.0) == "no-coverage"

    def test_mixed_results(self):
        results = [
            {"title": "FAQ: Docker", "score": 8.0, "status": "faq", "tags": ["faq"]},
            {"title": "Docker exit 137 debugging", "score": 12.0, "status": "published", "tags": ["docker"]},
        ]
        assert classify_results(results, 5.0) == "lesson-covered"
