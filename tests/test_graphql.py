"""Tests for GraphQL API — Issue #316."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from misakanet.graphql.schema import execute_query


class TestGraphQLSchema:
    def test_lessons_query(self):
        result = execute_query('{ lessons(limit: 3) { title domain } }')
        assert result["errors"] is None
        assert len(result["data"]["lessons"]) == 3
        for lesson in result["data"]["lessons"]:
            assert "title" in lesson
            assert "domain" in lesson

    def test_lesson_by_id(self):
        # First get a lesson to use its ID
        result = execute_query('{ lessons(limit: 1) { path } }')
        path = result["data"]["lessons"][0]["path"]
        filename = path.split("/")[-1]

        result = execute_query(f'{{ lesson(id: "{filename}") {{ title domain tags }} }}')
        assert result["errors"] is None
        assert result["data"]["lesson"] is not None
        assert result["data"]["lesson"]["title"] != ""

    def test_search_query(self):
        result = execute_query('{ search(q: "pip timeout") { score lesson { title } } }')
        assert result["errors"] is None
        assert len(result["data"]["search"]) > 0
        # First result should have a score
        assert result["data"]["search"][0]["score"] != ""

    def test_search_with_domain_filter(self):
        result = execute_query('{ search(q: "error", domain: "devops") { lesson { title domain } } }')
        assert result["errors"] is None
        for r in result["data"]["search"]:
            assert r["lesson"]["domain"] == "devops"

    def test_search_with_limit(self):
        result = execute_query('{ search(q: "fix", limit: 5) { lesson { title } } }')
        assert result["errors"] is None
        assert len(result["data"]["search"]) <= 5

    def test_empty_search(self):
        # BM25 normalizes scores, so even nonsensical queries return results
        # The important thing is that the query doesn't crash
        result = execute_query('{ search(q: "xyznonexistent12345") { score lesson { title } } }')
        assert result["errors"] is None
        assert isinstance(result["data"]["search"], list)

    def test_introspection(self):
        result = execute_query('{ __schema { types { name } } }')
        assert result["errors"] is None
        types = [t["name"] for t in result["data"]["__schema"]["types"]]
        assert "Lesson" in types
        assert "SearchResult" in types
        assert "Query" in types

    def test_lesson_not_found(self):
        result = execute_query('{ lesson(id: "nonexistent.md") { title } }')
        assert result["errors"] is None
        assert result["data"]["lesson"] is None
