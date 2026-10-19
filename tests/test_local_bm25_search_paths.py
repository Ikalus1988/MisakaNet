"""The local stdio server's BM25 path: memory_context, `domain`, and "usage" routing.

This is the path a fresh checkout uses: `data/sag.db` does not exist, so `_init_search()` picks
BM25. Three defects lived only here:

1. `misakanet_memory_context` imported `_load_docs_cached`, `_search_cached` and `LESSONS` from
   `misakanet.server._config`, which only imports them inside `_get_search_state()`. Every call
   failed with `ImportError` (JSON-RPC -32603).
2. `misakanet_search` (and memory_context) never applied `domain` on this path. SAG, the fallback
   and `MisakaNetSearchEngine.search` all filter on it.
3. `_EVIDENCE_INTENT_RE` still matched bare `usage`, so `docker disk usage full` routed to
   `kind="evidence"`, BM25 results carry no evidence fields, and every result was dropped. This
   is #3001 again: #3043 anchored the regex in the worker only.

The backend is forced explicitly (SAG off, BM25 on), so these tests do not depend on whether
`data/sag.db` happens to exist.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import pytest  # noqa: E402

from misakanet.server.handlers import memory_context as memctx_mod  # noqa: E402
from misakanet.server.handlers import search as search_mod  # noqa: E402

BM25_ONLY = (False, None, True, None)


@pytest.fixture
def bm25_only(monkeypatch):
    monkeypatch.setattr(memctx_mod, "_get_search_state", lambda: BM25_ONLY)
    monkeypatch.setattr(search_mod, "_get_search_state", lambda: BM25_ONLY)


def test_memory_context_returns_lessons_on_the_bm25_path(bm25_only):
    out = memctx_mod.handle_memory_context({"task": "pip install timeout behind corporate proxy"})
    assert "error" not in out
    assert out["lesson_count"] > 0
    assert out["lessons"][0]["path"]


def test_memory_context_applies_domain_on_the_bm25_path(bm25_only):
    out = memctx_mod.handle_memory_context({"task": "DCO sign-off failed", "domain": "feishu"})
    assert out["lessons"], "expected at least one feishu lesson"
    assert {r["domain"] for r in out["lessons"]} == {"feishu"}


def test_search_applies_domain_on_the_bm25_path():
    # Twice: the second call is served from `_search_cached`'s L1 cache, which keeps only the
    # top 20, so a filter applied after ranking would find nothing there.
    for _ in range(2):
        out = search_mod.handle_search(
            {"query": "DCO sign-off failed", "domain": "feishu", "top": 3, "detail": "summary"},
            search_state=BM25_ONLY,
        )
        assert out["source"] == "bm25"
        assert out["results"], "expected at least one feishu lesson"
        assert {r["domain"] for r in out["results"]} == {"feishu"}


def test_search_with_unknown_domain_returns_nothing():
    out = search_mod.handle_search(
        {"query": "DCO sign-off failed", "domain": "no-such-domain", "top": 3},
        search_state=BM25_ONLY,
    )
    assert out["results"] == []


@pytest.mark.parametrize(
    "query",
    ["docker disk usage full", "npm usage error", "Usage: pip install <pkg>"],
)
def test_usage_in_error_text_does_not_route_to_evidence(query):
    assert search_mod._detect_kind(query) != "evidence"


@pytest.mark.parametrize("query", ["usage count", "usage of it", "引用次数", "verification"])
def test_usage_count_still_routes_to_evidence(query):
    assert search_mod._detect_kind(query) == "evidence"


def test_query_with_usage_still_returns_lessons():
    out = search_mod.handle_search(
        {"query": "docker disk usage full", "top": 3}, search_state=BM25_ONLY
    )
    assert out["kind"] != "evidence"
    assert out["results"]
    assert not out.get("no_match")


def test_bm25_results_carry_tags_for_related():
    out = search_mod.handle_search(
        {"query": "security fix turns tests red credential leak", "top": 3, "detail": "summary"},
        search_state=BM25_ONLY,
    )
    assert any(r.get("tags") for r in out["results"])
