#!/usr/bin/env python3
"""Tests for the lessons.json keyword fallback (Issue #913).

When neither SAG-Lite nor BM25 is available, the MCP search tool falls
back to keyword matching over data/lessons.json (implemented in
mcp_server._fallback_search) and reports source "fallback" so callers
can distinguish the three modes. These tests pin the behaviour and
prevent regressions in the sandbox fallback path.
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pathlib import Path

import pytest

import scripts.mcp_server as mcp
from misakanet.server.handlers import search as search_mod


@pytest.fixture(autouse=True)
def no_engines(monkeypatch):
    """Force both SAG-Lite and BM25 to be unavailable.

    Patch _SEARCH_STATE in the handler module (single source of truth)
    rather than the compatibility-layer variables in mcp_server.
    """
    monkeypatch.setattr(
        search_mod, "_SEARCH_STATE", (False, Path("/nonexistent"), False, None)
    )
    yield


def test_fallback_returns_results_instead_of_error():
    resp = mcp.handle_search({"query": "MCP", "top": 5})
    assert "error" not in resp
    assert "results" in resp
    assert resp["source"] == "fallback"


def test_fallback_source_is_distinct():
    """The source field must be exactly 'fallback' (not sag-lite/bm25)."""
    resp = mcp.handle_search({"query": "MCP", "top": 3})
    assert resp["source"] == "fallback"


def test_fallback_results_have_lesson_shape():
    """Fallback results carry the documented shape (title/path/domain)."""
    resp = mcp.handle_search({"query": "sandbox", "top": 3, "detail": "full"})
    for r in resp["results"]:
        assert isinstance(r, dict)
        assert "title" in r
        assert "path" in r
        assert "domain" in r


def test_fallback_matches_real_content():
    """A query for a real lesson topic must return a relevant hit."""
    resp = mcp.handle_search({"query": "release notes", "top": 5})
    assert resp["results"], "expected at least one hit for 'release notes'"
    top = resp["results"][0]
    blob = " ".join(str(v).lower() for v in top.values())
    assert "release" in blob or "notes" in blob


def test_fallback_respects_top_limit():
    resp = mcp.handle_search({"query": "MCP", "top": 2})
    assert len(resp["results"]) <= 2


def test_fallback_empty_query_is_rejected():
    resp = mcp.handle_search({"query": "", "top": 5})
    assert "error" in resp


def test_fallback_domain_filter():
    """A domain filter narrows the fallback results."""
    resp = mcp.handle_search({"query": "MCP", "top": 20, "domain": "core", "detail": "full"})
    for r in resp["results"]:
        assert r.get("domain") == "core"


def test_sag_still_preferred_when_available(monkeypatch):
    """With SAG available, the source must be sag-lite (no fallback)."""

    def fake_sag(db, query, domain=None, top=5):
        return [{"id": "x", "title": query}]

    monkeypatch.setattr(
        search_mod, "_SEARCH_STATE", (True, Path("/nonexistent/sag.db"), False, fake_sag)
    )
    resp = mcp.handle_search({"query": "MCP", "top": 5})
    assert resp["source"] == "sag-lite"
