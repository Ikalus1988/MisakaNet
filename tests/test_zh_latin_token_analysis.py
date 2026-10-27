#!/usr/bin/env python3
"""Tests for `scripts/zh_latin_token_analysis.py` — the definitions, not the live probe.

Why these tests exist
---------------------
The analysis answers a question about a live probe (`.cache/zh-recall-probe-v2.json`), and
its answer is only as good as the definition it is computed with. A stoplist that grows
after the numbers are seen, a regex that splits `node.js` into `node` and `js`, or an
`explained_by_latin` that treats a *hit's* own target as a wrong hit would each move the
headline without moving the data. Those definitions, and the bucket arithmetic behind the
totals, are pinned here on synthetic fixtures.

No test reads `.cache/` and no test sends a query anywhere: the real numbers live in
`.cache/embed-ab/latin-token-analysis.json`, and CI must stay offline. The fixtures are
deliberately small enough to check by eye — the point is to make the definition auditable,
not to re-derive the probe.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts import zh_latin_token_analysis as analysis  # noqa: E402

# ── token extraction: the pattern, the stoplist, and what counts as "present" ──────────────────


def test_latin_tokens_keep_inner_dots_hyphens_plus_and_hash():
    text = "升级 node.js、docker-compose、c++、c#，再查 s7-1200 和 GitHub Actions 的 YAML"
    assert analysis.latin_tokens(text) == [
        "node.js",
        "docker-compose",
        "c++",
        "c#",
        "s7-1200",
        "github",
        "actions",
        "yaml",
    ]


def test_a_sentence_final_dot_is_punctuation_not_part_of_the_token():
    # The literal pattern would otherwise produce "node.js." and "actions.", which never
    # match the same words in another lesson; interior dots must survive.
    assert analysis.latin_tokens("Node.js. Actions.") == ["node.js", "actions"]
    assert analysis.token_set("GitHub Actions.") == {"github", "actions"}


def test_tokens_are_lowercased_and_deduplicated_per_query():
    assert analysis.latin_tokens("API api Api github GITHUB") == ["api", "github"]


def test_stoplist_is_exactly_the_documented_function_words():
    assert analysis.STOPLIST == frozenset(
        {"the", "and", "for", "with", "of", "to", "in", "on", "is", "it", "a", "an"}
    )
    assert analysis.latin_tokens("the AND for With of TO in on IS it a an") == []
    # Technical abbreviations must survive: they are the tokens under test.
    assert analysis.latin_tokens("AI CI PR API YAML") == ["ai", "ci", "pr", "api", "yaml"]


def test_presence_is_whole_token_membership_not_substring():
    assert analysis.token_set("said email wait") == {"said", "email", "wait"}
    assert "ai" not in analysis.token_set("said email wait")
    assert "ai" in analysis.token_set("the AI model")


# ── explained_by_latin: broad vs strict, and never for a hit or a no-hit ──────────────────────


def test_explained_by_latin_requires_a_wrong_hit_and_a_shared_token():
    assert analysis.explained_by_latin("wrong", ["ai"]) is True
    assert analysis.explained_by_latin(None, ["ai"]) is False
    assert analysis.explained_by_latin("wrong", []) is False


def test_strict_requires_more_overlap_than_the_target():
    assert analysis.explained_strict("wrong", ["github", "actions"], ["docker-compose"]) is True
    # Equal overlap is not "explained": the target holds the same token too.
    assert analysis.explained_strict("wrong", ["github"], ["github"]) is False
    assert analysis.explained_strict("wrong", ["github"], ["github", "actions"]) is False
    assert analysis.explained_strict(None, ["github"], []) is False


def test_analyze_row_separates_the_wrong_hit_from_the_target():
    corpus = {
        "target": {"id": "target", "text": "Run docker-compose locally."},
        "wrong": {"id": "wrong", "text": "GitHub Actions CI runs the tests."},
    }
    row = {
        "lesson_id": "target",
        "target_lang": "en",
        "overlap": "low",
        "query": "用 GitHub Actions 部署 docker-compose",
        "ids": ["wrong", "target"],
        "rank": None,
        "ok": True,
    }
    out = analysis.analyze_row(row, corpus, {"github": 5, "actions": 2, "docker-compose": 1})

    assert out["miss_kind"] == "wrong_hit"
    assert out["latin_tokens"] == ["github", "actions", "docker-compose"]
    assert out["target_has"] == ["docker-compose"]
    assert out["wrong_has"] == ["github", "actions"]
    assert out["explained_by_latin"] is True
    assert out["explained_strict"] is True
    assert out["token_document_frequency"]["github"] == 5
    assert out["wrong_hit"] == "wrong"


def test_a_hit_never_counts_its_own_target_as_a_wrong_hit():
    corpus = {"target": {"id": "target", "text": "GitHub Actions."}}
    row = {
        "lesson_id": "target",
        "target_lang": "en",
        "overlap": "high",
        "query": "GitHub Actions",
        "ids": ["target"],
        "rank": 1,
        "ok": True,
    }
    out = analysis.analyze_row(row, corpus)

    assert out["miss_kind"] == "hit"
    assert out["wrong_hit"] is None
    assert out["wrong_has"] == []
    assert out["explained_by_latin"] is False
    assert out["target_has"] == ["github", "actions"]


def test_no_ids_is_a_no_hit_and_cannot_be_explained_by_a_wrong_lesson():
    corpus = {"target": {"id": "target", "text": "GitHub Actions."}}
    row = {
        "lesson_id": "target",
        "target_lang": "en",
        "overlap": "low",
        "query": "GitHub Actions",
        "ids": [],
        "rank": None,
        "ok": True,
    }
    out = analysis.analyze_row(row, corpus)

    assert out["miss_kind"] == "no_hit"
    assert out["wrong_hit"] is None
    assert out["explained_by_latin"] is False


def test_missing_corpus_rows_are_flagged_not_silently_treated_as_no_overlap():
    row = {
        "lesson_id": "gone",
        "target_lang": "en",
        "overlap": "low",
        "query": "GitHub",
        "ids": ["also-gone"],
        "rank": None,
        "ok": True,
    }
    out = analysis.analyze_row(row, {})

    assert out["target_in_corpus"] is False
    assert out["wrong_hit_in_corpus"] is False
    assert out["explained_by_latin"] is False


# ── bucket aggregation: the table's arithmetic, on hand-countable fixtures ────────────────────


def analyzed(
    bucket: str,
    miss_kind: str,
    tokens: list[str] | None = None,
    explained: bool = False,
    strict: bool = False,
) -> dict:
    target_lang, overlap = bucket.split("/")
    return {
        "bucket": bucket,
        "target_lang": target_lang,
        "overlap": overlap,
        "miss_kind": miss_kind,
        "latin_tokens": tokens or [],
        "explained_by_latin": explained,
        "explained_strict": strict,
    }


def test_aggregate_counts_each_bucket_and_keeps_the_four_in_a_stable_order():
    rows = [
        analyzed("en/high", "hit", ["api"]),
        analyzed("en/high", "wrong_hit", ["ai"], explained=True),
        analyzed("en/high", "no_hit"),
        analyzed("en/low", "wrong_hit", ["ci"], explained=True, strict=True),
        analyzed("zh/high", "hit"),
        analyzed("zh/high", "wrong_hit", ["pr"], explained=True),
        analyzed("zh/low", "no_hit", ["docker-compose"]),
    ]
    groups = analysis.aggregate(rows)

    assert list(groups) == ["en/high", "en/low", "zh/high", "zh/low"]
    assert groups["en/high"] == {
        "queries": 3,
        "hits": 1,
        "misses": 2,
        "wrong_hit_misses": 1,
        "no_hit_misses": 1,
        "queries_with_latin_tokens": 2,
        "hits_with_latin_tokens": 1,
        "misses_with_latin_tokens": 1,
        "explained_by_latin": 1,
        "explained_strict": 0,
    }
    assert groups["en/low"] == {
        "queries": 1,
        "hits": 0,
        "misses": 1,
        "wrong_hit_misses": 1,
        "no_hit_misses": 0,
        "queries_with_latin_tokens": 1,
        "hits_with_latin_tokens": 0,
        "misses_with_latin_tokens": 1,
        "explained_by_latin": 1,
        "explained_strict": 1,
    }
    assert groups["zh/high"]["queries"] == 2
    assert groups["zh/high"]["hits"] == 1
    assert groups["zh/high"]["misses"] == 1
    assert groups["zh/high"]["explained_by_latin"] == 1
    assert groups["zh/low"]["misses"] == 1
    assert groups["zh/low"]["no_hit_misses"] == 1

    totals = analysis.sum_counts(groups.values())
    assert totals["queries"] == 7
    assert totals["hits"] == 2
    assert totals["misses"] == 5
    assert totals["wrong_hit_misses"] == 3
    assert totals["no_hit_misses"] == 2
    assert totals["queries_with_latin_tokens"] == 5
    assert totals["misses_with_latin_tokens"] == 4
    assert totals["explained_by_latin"] == 3
    assert totals["explained_strict"] == 1


def test_aggregate_by_language_uses_the_same_counters():
    rows = [
        analyzed("en/high", "hit"),
        analyzed("en/high", "wrong_hit", ["ai"], explained=True),
        analyzed("en/low", "wrong_hit", ["ci"], explained=True, strict=True),
        analyzed("en/low", "no_hit"),
        analyzed("zh/high", "hit"),
        analyzed("zh/low", "wrong_hit", ["pr"], explained=True),
    ]
    by_language = analysis.aggregate(rows, key=lambda row: row["target_lang"])

    assert by_language["en"]["queries"] == 4
    assert by_language["en"]["misses"] == 3
    assert by_language["en"]["explained_by_latin"] == 2
    assert by_language["en"]["explained_strict"] == 1
    assert by_language["zh"]["queries"] == 2
    assert by_language["zh"]["misses"] == 1
    assert by_language["zh"]["explained_by_latin"] == 1
    assert by_language["zh"]["explained_strict"] == 0


def test_a_latin_token_in_the_query_is_not_the_same_count_as_a_shared_wrong_hit():
    row = analyzed("en/low", "wrong_hit", ["yaml"], explained=False)
    counts = analysis.aggregate([row])["en/low"]

    assert counts["misses_with_latin_tokens"] == 1
    assert counts["explained_by_latin"] == 0


# ── the cache root and the probe join: no hard-coded home directory, no silent drift ───────────


def test_cache_dir_prefers_a_checkout_that_holds_the_probe(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".cache").mkdir(parents=True)
    (repo / ".cache" / analysis.PROBE_NAME).write_text("[]", encoding="utf-8")

    assert analysis.cache_dir_for(repo) == repo / ".cache"


def test_cache_dir_follows_a_linked_worktree_to_the_main_checkout(tmp_path):
    main = tmp_path / "main"
    worktree = tmp_path / "worktree"
    gitdir = main / ".git" / "worktrees" / "ab-token"
    gitdir.mkdir(parents=True)
    cache = main / ".cache"
    cache.mkdir()
    (cache / analysis.PROBE_NAME).write_text("[]", encoding="utf-8")
    worktree.mkdir()
    (worktree / ".git").write_text(f"gitdir: {gitdir}\n", encoding="utf-8")

    assert analysis.cache_dir_for(worktree) == cache


def test_default_cache_dir_honours_the_environment_override(monkeypatch, tmp_path):
    monkeypatch.setenv("MISAKANET_CACHE_DIR", str(tmp_path / "cache"))
    assert analysis.default_cache_dir() == tmp_path / "cache"


def test_join_reports_query_and_overlap_drift_instead_of_silently_joining():
    probe_rows = [{"lesson_id": "x", "query": "中文查询", "overlap": "high"}]
    zh_queries = {"x": {"lesson_id": "x", "query": "另一条查询", "overlap_bucket": "low"}}
    issues = analysis.check_join(probe_rows, zh_queries)

    assert len(issues) == 2
    assert any("query text differs" in issue for issue in issues)
    assert any("overlap" in issue for issue in issues)


def test_probe_contract_rejects_a_row_missing_ids(tmp_path):
    path = tmp_path / analysis.PROBE_NAME
    path.write_text(json.dumps([{"lesson_id": "x"}]), encoding="utf-8")

    with pytest.raises(analysis.AnalysisError, match="missing"):
        analysis.load_probe(path)
