#!/usr/bin/env python3
"""Generate the golden ranking snapshot for the **Python** retrieval engine.

    python3 scripts/gen_ranking_snapshot.py            # (re)write tests/fixtures/ranking-snapshot.json
    python3 scripts/gen_ranking_snapshot.py --check     # exit 1 if the fixture is not what we compute now

What it pins
    For a fixed query set, the ordered top-N lesson paths and their scores returned by
    ``misakanet.search.engine._rank_docs`` — the ranker behind ``search_knowledge.py`` and
    ``scripts/eval_query_aliases.py``, i.e. the local Python retrieval path. It says
    nothing about the JS/worker BM25 in ``workers/register-proxy-sw.js``.

Why it is here
    Before this file there was no test that could answer "did the ranking change?".
    That is why nobody dares restructure the retrieval code: every candidate edit is
    judged by eye. The snapshot turns that judgement into a diff.

Determinism — every environment-dependent input, and how it is handled
    1. No network, no model, no worker. ``_rank_docs`` reads ``lessons/`` from disk.
    2. Corpus order is ``misakanet.lesson_index.canonical_lessons()``, which sorts
       directories (core/contrib priority, then name) and files — not filesystem order.
    3. The mix weights are passed in explicitly (``PINNED_WEIGHTS``) rather than read from
       ``config.yaml``, so an untracked local config cannot move the snapshot.
       ``tests/test_ranking_snapshot.py`` separately asserts these are the shipped
       ``scripts.search_config.SearchConfig`` defaults, so a change to those defaults is
       still a red snapshot.
    4. The recency boost is pinned **off** by zeroing each doc's ``mtime``.
       ``engine._is_recent()`` compares ``datetime.now()`` with the file mtime, which is a
       property of the checkout (fresh clone == checkout time), not of the ranking code.
       In a fresh clone *every* file is inside the 30-day window, so ``BOOST_RECENT`` is the
       same +0.05 for the whole corpus — a uniform additive constant leaves the ordering
       unchanged — so pinning it off changes the pinned *scores* but not the pinned *order*.
       This is the one time-dependent score term; ``_relative_time()`` is formatting only
       and ``CachedDoc.score_baseline`` does not look at mtime.
    5. ``misakanet_core.compute_bm25`` sums per-term contributions in ``set(query_tokens)``
       order, which is hash-seed dependent. Scores are rounded to 6 decimals; the
       summation-order noise is ~1e-15 relative, far below that.

A change to the fixture means the Python retrieval ranking changed. That is a behaviour
change, not a formatting change: read the diff, decide whether it is intended, and only
then regenerate with the command above.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(REPO / "scripts"), str(REPO)]

FIXTURE = REPO / "tests" / "fixtures" / "ranking-snapshot.json"

# How many ranked lessons per query the snapshot pins. Longer lists are more sensitive to
# small weight changes (a top-3 can be identical while the tail reorders) but noisier when
# the corpus grows; 10 is the compromise, and every query in the set has >= 10 hits.
TOP_N = 10

# search_knowledge.py:451 `MIN_SCORE_THRESHOLD` — the floor the CLI applies before printing.
# Pinning it means the snapshot also pins "what counts as a result", not only the order.
MIN_SCORE = 0.1

# scripts/search_config.py SearchConfig defaults, passed explicitly (see docstring #3).
PINNED_WEIGHTS = {"bm25_weight": 0.65, "metadata_weight": 0.20, "baseline_weight": 0.15}

SCHEMA_VERSION = 1


def load_queries() -> list[tuple[str, str]]:
    """The pinned query set: ``(query, source)`` in a fixed order, de-duplicated.

    Both sources are already curated in this repo — the set is *selected*, not invented:

    * ``eval_query_aliases`` — the 20-query offline eval set of
      ``scripts/eval_query_aliases.py::QUERIES``. This is the set the comment in
      ``workers/register-proxy-sw.js`` ("11/20 of an offline eval set") refers to. Mostly
      Chinese questions spanning python / devops / k8s / git / feishu / fanuc.
    * ``regression_queries`` — the 11 English, error-text-shaped queries of
      ``data/regression_queries.json`` ("pip install timeout SSL error",
      "database is locked SQLite", ...) across 9 categories. The eval set is thin on the
      "paste a raw error" shape, which is how agents actually query, so it is added here.
    """
    from scripts.eval_query_aliases import QUERIES as EVAL_QUERIES

    fixture = json.loads((REPO / "data" / "regression_queries.json").read_text(encoding="utf-8"))

    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for query, *_rest in EVAL_QUERIES:
        if query not in seen:
            seen.add(query)
            pairs.append((query, "eval_query_aliases"))
    for entry in fixture["queries"]:
        query = entry["query"]
        if query not in seen:
            seen.add(query)
            pairs.append((query, "regression_queries"))
    return pairs


def corpus_fingerprint(docs) -> str:
    """sha256 over the sorted (repo-relative path, content) pairs of the indexed corpus.

    Recorded for diagnosis only — it is *not* asserted, because a new lesson that does not
    reach any pinned top-N is not a ranking change. When the snapshot does go red, this
    tells the reader at a glance whether the corpus or the code moved.
    """
    digest = hashlib.sha256()
    for doc in sorted(docs, key=lambda d: d.filepath.relative_to(REPO).as_posix()):
        rel = doc.filepath.relative_to(REPO).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(doc.content.encode("utf-8")).digest())
    return "sha256:" + digest.hexdigest()


def _load_pinned_docs():
    """Load the corpus with the recency boost pinned off (docstring #4)."""
    from misakanet.search.engine import LESSONS, _load_docs

    return [replace(doc, mtime=0.0) for doc in _load_docs(LESSONS, is_lesson=True)]


def rank(query: str, docs) -> list[dict]:
    """Top-N ``{path, score}`` above ``MIN_SCORE`` for one query (the pinned call)."""
    from misakanet.search.engine import _rank_docs

    ranked = _rank_docs(query, docs, weights=PINNED_WEIGHTS)
    hits = []
    for score, doc in ranked:
        if score < MIN_SCORE:
            continue
        hits.append({
            "path": doc.filepath.relative_to(REPO).as_posix(),
            "score": round(float(score), 6),
        })
        if len(hits) >= TOP_N:
            break
    return hits


def collect_snapshot() -> dict:
    """The full snapshot payload, exactly as written to the fixture."""
    docs = _load_pinned_docs()
    queries = load_queries()
    return {
        "_comment": [
            "GOLDEN RANKING SNAPSHOT — Python retrieval only. Do not hand-edit.",
            "",
            "Generated by:  python3 scripts/gen_ranking_snapshot.py",
            "Verified by:   python3 -m pytest tests/test_ranking_snapshot.py -q",
            "",
            "It pins, for a fixed query set, the ordered top-N lesson paths and scores that",
            "misakanet.search.engine._rank_docs returns. Generation and verification share the",
            "same code (scripts/gen_ranking_snapshot.py: collect_snapshot), so they cannot drift.",
            "",
            "Environment-dependent inputs are pinned, not sampled: no network/model; corpus order",
            "comes from lesson_index.canonical_lessons (sorted); mix weights are passed explicitly;",
            "the mtime-based recency boost is pinned OFF (see the generator docstring for why that",
            "cannot change the ORDER); scores are rounded to 6dp.",
            "",
            "IF THIS FILE CHANGES, THE PYTHON RANKING CHANGED. That is a behaviour change — read the",
            "diff and decide whether it is intended before regenerating. engine.py, misakanet-core,",
            "the SearchConfig defaults, the corpus, and the query sources can all move it.",
        ],
        "schema_version": SCHEMA_VERSION,
        "top_n": TOP_N,
        "min_score": MIN_SCORE,
        "pinned_weights": dict(PINNED_WEIGHTS),
        "recency_boost": "pinned off (mtime zeroed; order-neutral, see generator docstring)",
        "query_sources": [
            {
                "id": "eval_query_aliases",
                "path": "scripts/eval_query_aliases.py",
                "symbol": "QUERIES",
                "why": "the repo's 20-query offline eval set — the one the worker comment calls "
                       "'the offline eval set' (workers/register-proxy-sw.js)",
            },
            {
                "id": "regression_queries",
                "path": "data/regression_queries.json",
                "symbol": "queries",
                "why": "11 curated English error-text queries across 9 categories; the eval set is "
                       "thin on the raw-error shape agents actually paste",
            },
        ],
        "corpus": {
            "lesson_count": len(docs),
            "fingerprint": corpus_fingerprint(docs),
        },
        "queries": [
            {"query": query, "source": source, "results": rank(query, docs)}
            for query, source in queries
        ],
    }


def write_fixture(payload: dict) -> None:
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true",
                        help="compare against the committed fixture instead of writing it")
    args = parser.parse_args(argv)

    payload = collect_snapshot()
    if args.check:
        if not FIXTURE.exists():
            print(f"missing fixture: {FIXTURE}", file=sys.stderr)
            return 1
        current = json.loads(FIXTURE.read_text(encoding="utf-8"))
        if current != payload:
            print("ranking-snapshot.json is stale — regenerate with:\n"
                  "  python3 scripts/gen_ranking_snapshot.py", file=sys.stderr)
            return 1
        print(f"ranking-snapshot.json is up to date ({len(payload['queries'])} queries)")
        return 0

    write_fixture(payload)
    rows = sum(len(q["results"]) for q in payload["queries"])
    print(f"wrote {FIXTURE.relative_to(REPO)}: {len(payload['queries'])} queries, {rows} pinned rows, "
          f"{payload['corpus']['lesson_count']} lessons")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
