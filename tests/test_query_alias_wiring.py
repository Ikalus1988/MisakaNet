"""Wiring tests for the query alias layer (issue #1780).

`data/query-aliases.json` used to be a library plus an offline eval: the local engine had
its own hard-coded `_SYNONYM_MAP` (Feature #532) and the Worker had no expansion at all,
which is why Chinese questions reached `searchLessonsBM25` with zero terms and returned
nothing. These tests cover the wiring itself:

* the Worker's inlined copy of the table is still the table (drift guard);
* `engine._expand_query` reads that file, and `_SYNONYM_MAP` is a *view* of it, not a
  second word list — removing an entry from the file removes it from both;
* the `MISAKANET_QUERY_ALIASES=0` rollback switch turns it off in the CLI and the engine;
* the regression fixtures (`data/regression_queries.json`) do not get worse, and empty or
  pure-English queries are unaffected.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import expand_query  # noqa: E402
import misakanet.search.engine as engine  # noqa: E402
import search_knowledge  # noqa: E402
from scripts import expand_query as engine_expand_query  # noqa: E402  (the module the engine reads)

WORKER = REPO / "workers" / "register-proxy-sw.js"
TABLE = REPO / "data" / "query-aliases.json"


@pytest.fixture(scope="module")
def docs():
    """The real corpus, loaded once: the regression fixtures are about real lessons."""
    return engine._load_docs(engine.LESSONS, is_lesson=True)


def _ranked(query: str, docs):
    engine._L1_CACHE.clear()          # the L1 cache is keyed by the raw query
    return [(s, d) for s, d in engine._rank_docs(query, docs) if s >= 0.1]


def _rel(doc) -> str:
    return doc.filename


# ── the Worker's copy of the file ───────────────────────────────────────────

def _worker_source() -> str:
    return WORKER.read_text(encoding="utf-8")


def test_worker_inlines_the_projection_of_the_alias_table():
    """A Worker cannot read a file at runtime, so the table is inlined. This recomputes
    the projection (the same one `--emit-worker-table` prints) and compares."""
    source = _worker_source()
    match = re.search(r"^const QUERY_ALIAS_TABLE = (\{.*\});$", source, re.M)
    assert match, "QUERY_ALIAS_TABLE is no longer a single-line JSON constant"
    assert json.loads(match.group(1)) == expand_query.worker_table(expand_query.cached_table())


def test_worker_expansion_constants_track_the_shared_ones():
    source = _worker_source()
    version = re.search(r"^const QUERY_ALIAS_VERSION = (\d+);", source, re.M)
    cap = re.search(r"^const QUERY_ALIAS_MAX_EXPANSIONS = (\d+);", source, re.M)
    assert version and int(version.group(1)) == expand_query.cached_table()["schema"]["version"]
    assert cap and int(cap.group(1)) == expand_query.MAX_EXPANSIONS


def test_worker_stopword_list_matches_the_expansion_stopwords():
    """`expand` rejects added terms that the Worker's BM25 tokenizer would drop; if the
    two lists drift, the Worker injects terms its own index cannot hold."""
    source = _worker_source()
    block = re.search(r"const BM25_STOPWORDS = new Set\(\[(.*?)\]\);", source, re.S)
    assert block, "BM25_STOPWORDS moved"
    js_words = set(re.findall(r'"([a-z]+)"', block.group(1)))
    assert js_words == expand_query._STOP_EN
    assert js_words == set(expand_query._STOP_EN)


# ── one word list, not two ──────────────────────────────────────────────────

def test_engine_reads_the_alias_table_and_a_removed_entry_changes_the_expansion(monkeypatch):
    """The point of the unification: delete an entry from data/query-aliases.json and the
    engine's expansion loses that term. (A hard-coded second word list would not move.)"""
    table = json.loads(TABLE.read_text(encoding="utf-8"))
    alias = "内存泄漏"
    assert alias in [e["alias"] for e in table["aliases"]]
    assert "memory" in engine._expand_query("内存泄漏")

    trimmed = dict(table, aliases=[e for e in table["aliases"] if e["alias"] != alias])
    # The engine imports the module as `scripts.expand_query`; patch *that* object.
    monkeypatch.setattr(engine_expand_query, "cached_table",
                        lambda path=engine_expand_query.DEFAULT_TABLE: trimmed)
    assert "memory" not in engine._expand_query("内存泄漏")


def test_synonym_map_is_a_view_of_the_table_not_a_second_list():
    table = expand_query.cached_table()
    by_alias: dict[str, set] = {}
    for entry in table["aliases"]:
        by_alias.setdefault(entry["alias"].strip().lower(), set()).add(entry["canonical"])
    assert engine._SYNONYM_MAP, "the legacy view is empty — the table did not load"
    for alias, canonicals in engine._SYNONYM_MAP.items():
        assert alias in by_alias, f"{alias!r} is not in the table"
        for canonical in canonicals:
            assert canonical in by_alias[alias], f"{alias!r} -> {canonical!r} is not the table's entry"


def test_legacy_terms_still_have_synonyms():
    """Feature #532's callers (/tests/test_synonym_expansion.py) keep working: the terms
    the old map covered are still covered, now by the shared file."""
    for term in ["mcp", "gbk", "dco", "pip", "git", "auth", "cron", "wsl"]:
        assert term in engine._SYNONYM_MAP, f"Missing synonym entry for {term}"
        assert engine._SYNONYM_MAP[term]


# ── the rollback switch ─────────────────────────────────────────────────────

def test_switch_off_makes_expansion_the_identity(monkeypatch):
    query = "如何切换识图模型"
    assert engine._expand_query(query) != query
    monkeypatch.setenv(expand_query.QUERY_ALIASES_ENV, "0")
    assert engine._expand_query(query) == query
    assert search_knowledge._scoring_query(query) == query


@pytest.mark.parametrize("value,enabled", [("", True), ("1", True), ("on", True),
                                           ("0", False), ("false", False), ("off", False),
                                           ("no", False), ("NO", False)])
def test_switch_values(value, enabled):
    assert expand_query.query_aliases_enabled(value) is enabled


def test_the_cli_and_the_engine_use_the_same_expansion(monkeypatch):
    """`search_knowledge.py` expands at the query entry; `_expand_query` is what it calls,
    so the two paths cannot disagree about the word list."""
    for query in ["如何切换识图模型", "中文乱码怎么解决", "mcp tool not showing"]:
        assert search_knowledge._scoring_query(query) == engine._expand_query(query)


def test_the_cli_ranking_is_what_the_offline_eval_measures(docs):
    """`search_knowledge.py` expands at its query entry and hands that string to
    `_rank_docs`, which expands too (the engine is the entry point for every other
    caller). So the CLI scores exactly what `scripts/eval_query_aliases.py` scores in its
    after column — the expanded string going through `_rank_docs` — which is what makes
    the eval's numbers a statement about the shipped CLI rather than about a library.
    """
    for query in ["如何切换识图模型", "中文乱码怎么解决", "DCO 签名失败怎么办",
                  "mcp tool not showing", "git TLS 握手失败"]:
        assert search_knowledge._scoring_query(query) == engine._expand_query(query)

        # The CLI path (CLI expansion, then the engine's own entry) …
        engine._L1_CACHE.clear()
        via_cli = engine._rank_docs(search_knowledge._scoring_query(query), docs)
        # … must equal the eval's after column, which is the same two entries in the same
        # order (expand once, then rank the expanded string).
        engine._L1_CACHE.clear()
        via_eval = engine._rank_docs(expand_query.expand_query_text(query), docs)
        assert [(round(s, 9), d.filename) for s, d in via_cli] == \
               [(round(s, 9), d.filename) for s, d in via_eval], query


def test_a_second_expansion_pass_only_adds_terms():
    """Not every query is a fixed point: when the translating layer consumes the CJK, a
    second pass can find no translation and fall to the migrated #532 co-occurrence layer
    (`超时` → `timeout` → the `timeout` entry's `ssl proxy`). That is the pass the CLI
    path picks up from `_rank_docs` — and it may only *add* terms, never drop one the
    first pass produced.
    """
    queries = [q for q, *_ in __import__("eval_query_aliases").QUERIES]
    queries += [q["query"] for q in json.loads(
        (REPO / "data" / "regression_queries.json").read_text(encoding="utf-8"))["queries"]]
    queries += ["mcp tool not showing", "pip timeout", "gbk error", "path traversal", ""]
    for query in queries:
        once = expand_query.expand_query_text(query)
        twice = expand_query.expand_query_text(once)
        assert set(expand_query.tokenize(once)) <= set(expand_query.tokenize(twice)), query
    queries = [q for q, *_ in __import__("eval_query_aliases").QUERIES]
    queries += [q["query"] for q in json.loads(
        (REPO / "data" / "regression_queries.json").read_text(encoding="utf-8"))["queries"]]
    queries += ["mcp tool not showing", "pip timeout", "gbk error", "path traversal", ""]
    for query in queries:
        once = expand_query.expand_query_text(query)
        twice = expand_query.expand_query_text(once)
        assert set(expand_query.tokenize(once)) <= set(expand_query.tokenize(twice)), query


# ── empty / English-only queries ────────────────────────────────────────────

def test_empty_and_whitespace_queries_are_left_alone():
    assert engine._expand_query("") == ""
    assert search_knowledge._scoring_query("") == ""
    assert expand_query.expand_query_text("") == ""
    assert engine._expand_query("   ") == ""


def test_pure_english_queries_keep_every_term_they_came_with():
    fixtures = json.loads((REPO / "data" / "regression_queries.json").read_text(encoding="utf-8"))
    for item in fixtures["queries"]:
        before = set(expand_query.worker_tokens(item["query"]))
        after = set(expand_query.worker_tokens(expand_query.expand_query_text(item["query"])))
        assert before <= after, f"{item['id']}: {sorted(before - after)} was dropped"


def test_the_expansion_does_not_match_inside_a_longer_word():
    """Raw substring matching made `pat` match `path`, `pr` match `proxy` and `sse` match
    `assets`, so an unrelated expansion was injected (found while wiring #1780)."""
    for query in ["path traversal", "patch the config", "assets pipeline", "storage backend",
                  "print the report", "drag and drop"]:
        assert expand_query.expand_query_text(query) == " ".join(expand_query.tokenize(query)), query


# ── the regression fixtures ─────────────────────────────────────────────────

def test_regression_fixtures_still_find_their_lessons(docs, monkeypatch):
    """`data/regression_queries.json` is the repo's curated "these must stay findable"
    set. Expansion may not drop a fixture lesson or cut the result count below its floor.

    Measured against the pre-#1780 engine (Feature #532's `_SYNONYM_MAP`), the unified
    layer returns the *same* expected-lesson ranks for all eleven fixtures — the `related`
    entries are that map, migrated — so this test is a floor, not a new bar.
    """
    fixtures = json.loads((REPO / "data" / "regression_queries.json").read_text(encoding="utf-8"))
    monkeypatch.delenv(expand_query.QUERY_ALIASES_ENV, raising=False)
    for item in fixtures["queries"]:
        ranked = _ranked(item["query"], docs)
        names = [_rel(doc) for _, doc in ranked]
        assert len(ranked) >= item["min_results"], f"{item['id']}: {len(ranked)} results"
        for expected in item["expected_lessons"]:
            assert any(name in expected or expected.endswith(name) for name in names), \
                f"{item['id']}: {expected} is no longer retrievable"


def test_regression_fixtures_do_not_lose_expected_lessons_with_expansion(docs, monkeypatch):
    """The switch-on run must not find fewer fixture lessons than the switch-off run."""
    fixtures = json.loads((REPO / "data" / "regression_queries.json").read_text(encoding="utf-8"))
    for item in fixtures["queries"]:
        monkeypatch.delenv(expand_query.QUERY_ALIASES_ENV, raising=False)
        on = [_rel(doc) for _, doc in _ranked(item["query"], docs)]
        monkeypatch.setenv(expand_query.QUERY_ALIASES_ENV, "0")
        off = [_rel(doc) for _, doc in _ranked(item["query"], docs)]
        expected = item["expected_lessons"]
        found_on = [e for e in expected if any(n in e or e.endswith(n) for n in on)]
        found_off = [e for e in expected if any(n in e or e.endswith(n) for n in off)]
        assert len(found_on) >= len(found_off), f"{item['id']}: {found_off} → {found_on}"
