#!/usr/bin/env python3
"""Golden ranking snapshot for the Python retrieval engine.

`tests/fixtures/ranking-snapshot.json` pins the ordered top-N lesson paths (and scores)
that ``misakanet.search.engine._rank_docs`` returns for a fixed query set. Generation and
verification share one code path — ``scripts/gen_ranking_snapshot.py:collect_snapshot`` —
so the fixture cannot drift from how it is checked.

Regenerate (after deciding the change is intended):

    python3 scripts/gen_ranking_snapshot.py

This module is offline and deterministic. The generator docstring lists every
environment-dependent input and how it is pinned; the short version: no network/model, the
corpus is loaded in sorted order, the mix weights are passed explicitly, the mtime-based
recency boost is pinned off (order-neutral, see the docstring), and the JS/worker BM25 is
deliberately *not* covered here.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts import gen_ranking_snapshot  # noqa: E402  (needs REPO on sys.path)
from scripts.gen_ranking_snapshot import (  # noqa: E402
    FIXTURE,
    MIN_SCORE,
    PINNED_WEIGHTS,
    TOP_N,
    collect_snapshot,
    load_queries,
)

REGENERATE = "python3 scripts/gen_ranking_snapshot.py"


# ── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def committed() -> dict:
    """The fixture as committed to the repository."""
    assert FIXTURE.exists(), (
        f"{FIXTURE.relative_to(REPO)} is missing — generate it with: {REGENERATE}"
    )
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def live() -> dict:
    """The snapshot the current working tree produces (computed once per session)."""
    return collect_snapshot()


def _by_query(payload: dict) -> dict[str, dict]:
    return {entry["query"]: entry for entry in payload["queries"]}


def _diagnosis(committed: dict, live: dict) -> str:
    """Corpus context for a failure message: did the corpus or the code move?"""
    c, l = committed["corpus"], live["corpus"]
    same = c["fingerprint"] == l["fingerprint"]
    line = (
        f"corpus: committed {c['lesson_count']} lessons, current {l['lesson_count']} lessons, "
        f"content {'unchanged' if same else 'CHANGED'}"
    )
    if not same:
        line += " — a lesson was added/edited/removed; that alone can reorder results."
    else:
        line += " — the corpus is identical, so the ranking *code/weights* moved."
    return line


# ── the pinned behaviour ─────────────────────────────────────────────────────

def test_ranking_topn_order_matches_snapshot(committed: dict, live: dict) -> None:
    """The headline gate: same top-N lesson paths, in the same order, for every query."""
    before, now = _by_query(committed), _by_query(live)

    assert set(before) == set(now), (
        "the pinned query set changed — regenerate:\n  " + REGENERATE
    )

    problems = []
    for query in now:
        expected = [r["path"] for r in before[query]["results"]]
        actual = [r["path"] for r in now[query]["results"]]
        if expected != actual:
            problems.append(
                f"\nquery: {query!r}\n"
                f"  committed: {expected}\n"
                f"  current  : {actual}"
            )

    assert not problems, (
        f"the Python retrieval ranking changed for {len(problems)}/{len(now)} queries.\n"
        + _diagnosis(committed, live)
        + "\nIf this is intended, regenerate and review the diff:\n  " + REGENERATE
        + "".join(problems)
    )


def test_ranking_scores_match_snapshot(committed: dict, live: dict) -> None:
    """Scores too: catches a weight move that reorders nothing but still changes ranking."""
    before, now = _by_query(committed), _by_query(live)

    for query in now:
        expected = [(r["path"], r["score"]) for r in before[query]["results"]]
        actual = [(r["path"], r["score"]) for r in now[query]["results"]]
        assert [p for p, _ in expected] == [p for p, _ in actual], (
            f"path list differs for {query!r} — see test_ranking_topn_order_matches_snapshot"
        )
        for (path, want), (_, got) in zip(expected, actual):
            assert got == pytest.approx(want, abs=1e-6), (
                f"score moved for {query!r} / {path}: committed {want}, current {got}\n"
                + _diagnosis(committed, live)
                + f"\nIf this is intended, regenerate:\n  {REGENERATE}"
            )


def test_snapshot_is_not_trivially_empty(committed: dict) -> None:
    """A broken ranker returning nothing must not be able to satisfy the snapshot."""
    assert committed["queries"], "the fixture pins no queries"
    for entry in committed["queries"]:
        results = entry["results"]
        assert len(results) == TOP_N, (
            f"{entry['query']!r} pins {len(results)} results, expected {TOP_N} — "
            f"regenerate:\n  {REGENERATE}"
        )
        for row in results:
            assert row["path"].startswith("lessons/"), f"not a lesson path: {row['path']!r}"
            assert row["score"] >= MIN_SCORE, (
                f"{row['path']!r} scored {row['score']} below the pinned floor {MIN_SCORE}"
            )


# ── the snapshot's own inputs, so drift in *those* is not silent ─────────────

def test_fixture_pins_the_generator_constants(committed: dict) -> None:
    """If TOP_N/MIN_SCORE/weights move in the generator, the fixture must be regenerated."""
    assert committed["schema_version"] == gen_ranking_snapshot.SCHEMA_VERSION
    assert committed["top_n"] == TOP_N
    assert committed["min_score"] == MIN_SCORE
    assert committed["pinned_weights"] == PINNED_WEIGHTS


def test_pinned_weights_are_the_shipped_search_config_defaults() -> None:
    """The snapshot pins explicit weights; assert they are still the shipped defaults.

    Without this, changing `scripts/search_config.SearchConfig` defaults would silently stop
    being covered — the explicit `weights=` argument would keep the snapshot green while
    production ranking moved.
    """
    from scripts.search_config import SearchConfig

    defaults = SearchConfig()
    assert PINNED_WEIGHTS == {
        "bm25_weight": defaults.bm25_weight,
        "metadata_weight": defaults.metadata_weight,
        "baseline_weight": defaults.baseline_weight,
    }, (
        "SearchConfig defaults changed, so production ranking changed while the snapshot pins "
        f"the old values ({PINNED_WEIGHTS}). Update PINNED_WEIGHTS and regenerate:\n  " + REGENERATE
    )


def test_query_set_is_the_two_curated_repo_sets() -> None:
    """The pinned queries are exactly the union of the repo's two curated sets, in order.

    Both sources are versioned in this repo, so a query added/removed/reworded there must be
    reflected in the fixture rather than silently leaving a stale expectation behind.
    """
    from scripts.eval_query_aliases import QUERIES as EVAL_QUERIES

    regression = json.loads(
        (REPO / "data" / "regression_queries.json").read_text(encoding="utf-8")
    )

    expected: list[str] = []
    for query in [q for q, *_ in EVAL_QUERIES] + [e["query"] for e in regression["queries"]]:
        if query not in expected:  # load_queries() keeps the first occurrence
            expected.append(query)

    assert [q for q, _ in load_queries()] == expected, (
        f"a curated query source changed — regenerate:\n  {REGENERATE}"
    )
