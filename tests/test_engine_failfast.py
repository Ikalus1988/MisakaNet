#!/usr/bin/env python3
"""Fail-fast guards for `misakanet/search/engine.py`.

Three defects lived in that module at once; this file pins the fixes.

**BM25 failure was indistinguishable from "no match".** `_compute_bm25_scores` wrapped the
whole core call in `except Exception` and returned `[0.0] * len(docs)`. A crashed ranker
therefore produced the exact same value as a query whose tokens match nothing, and every
caller treated it as a legitimate score vector — the search silently degraded to metadata
ordering. That is the "crash must look like a crash" rule in CLAUDE.md. The failure is now
raised as `BM25ScoringError`; the tests below force the core to raise and require the
failure to stay visible all the way to the MCP handler, which must *not* return a
`no_match` payload in its place.

**`K1` / `B` were dead constants.** AST-checked: module-level `Store` only, zero `Load`
anywhere in the repository, not in `__all__`. The core engine owns its own `k1`/`b`.

**The hard-coded `_SYNONYM_MAP` literal was dead code.** It sat at module top and was
unconditionally rebound at import to `_synonym_view()` — a projection of
`data/query-aliases.json` (the SSOT, 180 aliases at the time of the fix, vs the literal's
34). No read path ever observed the literal.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import misakanet.search.engine as engine  # noqa: E402
from misakanet.search.engine import (  # noqa: E402
    BM25ScoringError,
    CachedDoc,
    _compute_bm25_scores,
)

ENGINE_SRC = REPO / "misakanet" / "search" / "engine.py"


def _doc(name: str, content: str = "pip install timeout behind a corporate proxy") -> CachedDoc:
    return CachedDoc(
        filename=name,
        filepath=Path("lessons") / name,
        content=content,
        title=name,
        domain="python",
        status="published",
    )


@pytest.fixture
def exploding_bm25(monkeypatch):
    """Make the BM25 core fail the way a real core failure does: by raising."""

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated BM25 core failure")

    monkeypatch.setattr(engine, "BM25", _boom)
    return _boom


# ── (1) a scoring failure is not a zero score ────────────────────────────────

def test_bm25_core_failure_raises_instead_of_returning_zeros(exploding_bm25):
    """The regression: this used to return `[0.0, 0.0]` and print to stderr."""
    docs = [_doc("a.md"), _doc("b.md")]

    with pytest.raises(BM25ScoringError) as excinfo:
        _compute_bm25_scores("timeout behind proxy", docs)

    message = str(excinfo.value)
    assert "simulated BM25 core failure" in message, message
    assert "2 document(s)" in message, message
    # The original exception is chained, so the traceback still shows the real cause.
    assert isinstance(excinfo.value.__cause__, RuntimeError)


def test_zero_scores_still_mean_no_match(exploding_bm25):
    """The failure must not be confused with the legitimate all-zero case.

    `exploding_bm25` is patched but never reached: an empty query and a query with no
    tokens are *not* failures and must keep returning zeros without touching the core.
    """
    docs = [_doc("a.md"), _doc("b.md")]
    assert _compute_bm25_scores("", docs) == [0.0, 0.0]
    assert _compute_bm25_scores("   ", docs) == [0.0, 0.0]
    assert _compute_bm25_scores("!!!", docs) == [0.0, 0.0]


def test_unmatched_query_is_zero_scores_not_an_error():
    """Positive control with the real core: "no token matched" stays a value, not a raise."""
    docs = [_doc("a.md"), _doc("b.md", content="completely unrelated words here")]
    scores = _compute_bm25_scores("zzzqqq nonexistenttoken", docs)
    assert scores == [0.0, 0.0]


def test_ranking_path_propagates_the_failure(exploding_bm25):
    """`_rank_docs` (the public entry) must fail, not rank on metadata alone."""
    engine._L1_CACHE.clear()
    docs = [_doc("a.md"), _doc("b.md")]

    with pytest.raises(BM25ScoringError):
        engine._rank_docs("timeout behind proxy", docs)


def test_search_handler_surfaces_the_failure_instead_of_a_no_match(exploding_bm25):
    """The MCP boundary must not flatten an engine crash into "no results".

    `misakanet/server/handlers/search.py` has two broad `except Exception` blocks
    (:52-62 gap logging, :113-118 fallback JSON loading); neither wraps the BM25 call at
    :414-423. So the failure propagates to the request boundary, which reports it (stdio:
    JSON-RPC `-32603` in `misakanet/server/protocol.py:189`; adapter: `source: "error"`).
    """
    from misakanet.server.handlers import search as search_mod

    engine._L1_CACHE.clear()
    # Explicit state: SAG off, BM25 on — force the BM25 branch regardless of data/sag.db.
    state = (False, None, True, None)

    with pytest.raises(BM25ScoringError):
        search_mod.handle_search(
            {"query": "timeout behind proxy", "top": 3}, search_state=state
        )


# ── (2) the dead k1/b constants stay deleted ─────────────────────────────────

def test_dead_bm25_parameter_constants_are_gone():
    """`K1`/`B` had zero reads (AST: Store-only) — the core owns its own k1/b.

    If a future change genuinely needs module-level k1/b, give it a reader and change this
    test in the same commit; re-adding them without one is the defect this pins.
    """
    assert not hasattr(engine, "K1"), "K1 was reintroduced but has no reader"
    assert not hasattr(engine, "B"), "B was reintroduced but has no reader"


# ── (3) one synonym table, and it is the SSOT view ───────────────────────────

def test_synonym_map_has_exactly_one_binding_and_it_reads_the_ssot():
    """The dead literal must not come back as a second word list."""
    tree = ast.parse(ENGINE_SRC.read_text(encoding="utf-8"))
    bindings = [
        node
        for node in tree.body
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        and any(
            getattr(target, "id", None) == "_SYNONYM_MAP"
            for target in (
                node.targets if isinstance(node, ast.Assign) else [node.target]
            )
        )
    ]
    assert len(bindings) == 1, (
        f"{[b.lineno for b in bindings]} bind `_SYNONYM_MAP`; the module must define it once, "
        "as the view of data/query-aliases.json"
    )
    value = bindings[0].value
    assert isinstance(value, ast.Call), f"line {bindings[0].lineno} is not a call"
    assert getattr(value.func, "id", None) == "_synonym_view", (
        f"line {bindings[0].lineno} does not bind _SYNONYM_MAP to _synonym_view(); "
        "the alias table's SSOT is data/query-aliases.json"
    )


def test_synonym_map_matches_the_alias_table():
    """Runtime counterpart: the live map is the table, not a stale 34-entry copy."""
    from scripts import expand_query

    table = expand_query.cached_table()
    expected: dict[str, list[str]] = {}
    for entry in table.get("aliases", []):
        alias = str(entry.get("alias", "")).strip().lower()
        canonical = str(entry.get("canonical", "")).strip()
        if alias and canonical:
            expected.setdefault(alias, []).append(canonical)

    assert expected, "data/query-aliases.json produced no aliases"
    assert engine._SYNONYM_MAP == expected
