#!/usr/bin/env python3
"""Quantify the "Latin-token false match" explanation for Chinese retrieval misses.

Why this exists
---------------
The worker's BM25 tokenizer keeps Latin tokens and, since CJK-1 (#2355), adds character
bigrams for CJK. A Chinese query that also carries a Latin technical token ("GitHub
Actions", "CDP", "docker-compose") can therefore score an English lesson on that Latin
token even when the Chinese half of the query matches nothing in it. If that lesson
outranks the intended one, the miss is a cross-lingual failure with a lexical cause —
and the semantic fallback never gets a chance, because it is gated on an EMPTY BM25
result.

That story is plausible, and it was used to explain the 2026-10-27 Chinese-query probe
(`.cache/zh-recall-probe-v2.json`: 64 rows, 63 usable). This script tests the story on
that probe instead of repeating it. A refutation is as useful as a confirmation here, so
the token definition is fixed before looking at the answer and is printed with the
result: the check is auditable, not tuned.

Definitions (also written into the JSON under `definitions`)
------------------------------------------------------------
* **Latin token** — maximal match of `[A-Za-z][A-Za-z0-9_+.#-]{1,}`, lowercased,
  deduplicated per query. Dots, hyphens, `+` and `#` stay inside the token, so
  `node.js`, `docker-compose`, `c++` and `c#` are single tokens; `s7-1200` too.
  A trailing `.` is stripped as sentence punctuation (`Actions.` -> `actions`), because
  otherwise every sentence-final technical token would silently fail to match.
* **Stoplist** — the twelve pure-English function words {the, and, for, with, of, to,
  in, on, is, it, a, an}. Kept small and printed, so "the query had a Latin token" does
  not become true for every sentence that happens to contain "the". Technical
  abbreviations such as `ai`, `ci`, `pr`, `api` are deliberately NOT stopped: they are
  exactly the tokens the hypothesis is about.
* **Token presence** — a query token is present in a lesson when the lesson text,
  tokenized with the same pattern and stoplist, contains the same whole token. Substring
  hits do not count: `ai` is not present in "said" or "email". That is the conservative
  reading of "the wrong lesson matched on that token", and it avoids inflating overlap
  through English prose.
* **`explained_by_latin`** (broad) — the row is a miss, it returned a top-1 lesson, and
  at least one query Latin token is present in that top-1 lesson.
* **`explained_strict`** — additionally, the top-1 lesson holds STRICTLY MORE of the
  query's Latin tokens than the target lesson does. This is the "Latin overlap chose the
  wrong lesson over the right one" reading; the broad count can be true even when the
  target holds every one of those tokens too, in which case the token does not
  discriminate between the two lessons.

What the script can and cannot see
----------------------------------
The audit text is the 649-lesson snapshot in `.cache/embed-ab/corpus.json`. The live
index may tokenize fields slightly differently, so "present" is measured on the
snapshot. 289 of the 649 lessons contain Chinese sections, so `target_lang: en` means
the lesson's primary language, not that it has no Chinese text; that is why the JSON also
records CJK-bigram overlap as an auxiliary channel — a wrong hit can be bridged by
Chinese in the lesson rather than by a Latin token. The probe records only returned ids,
not BM25 scores, so NO row can be attributed to one token's score contribution. What is
measurable is the overlap that the story requires; this script reports that overlap and
stops there.

One row of the probe is a transport failure (`ok: false`, curl rc 56). It is excluded
from every count and the exclusion is printed and recorded in the JSON. The probe's 64
rows join 1:1 with the 64 `lang == "zh"` rows of `.cache/embed-ab/queries.json` on
`lesson_id`; the join is re-checked, and mismatches would be reported rather than
silently joined.

Usage:
    python3 scripts/zh_latin_token_analysis.py                 # human table
    python3 scripts/zh_latin_token_analysis.py --json          # machine summary
    python3 scripts/zh_latin_token_analysis.py --dir <cache>   # explicit cache root
    python3 scripts/zh_latin_token_analysis.py --output <file> # explicit JSON target

The JSON is always written (default: `<cache>/embed-ab/latin-token-analysis.json`); with
`--json` it is also the only thing on stdout.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROBE_NAME = "zh-recall-probe-v2.json"
CORPUS_REL = Path("embed-ab") / "corpus.json"
QUERIES_REL = Path("embed-ab") / "queries.json"
OUTPUT_REL = Path("embed-ab") / "latin-token-analysis.json"

LATIN_TOKEN_PATTERN = r"[A-Za-z][A-Za-z0-9_+.#-]{1,}"
LATIN_TOKEN_RE = re.compile(LATIN_TOKEN_PATTERN)
STOPLIST = frozenset({"the", "and", "for", "with", "of", "to", "in", "on", "is", "it", "a", "an"})
CJK_RUN_RE = re.compile(r"[\u4e00-\u9fff]+")

# Fixed order so the human table is stable even when a bucket has zero rows.
CANONICAL_BUCKETS = (("en", "high"), ("en", "low"), ("zh", "high"), ("zh", "low"))


class AnalysisError(RuntimeError):
    """An input is missing or shaped differently than the probe contract promises."""


# ── the definition: one regex, one stoplist, one tokenizer for query and lesson ────────────────


def latin_tokens(text: str) -> list[str]:
    """Query tokens: maximal Latin matches, lowercased, stoplisted, first-seen order.

    The literal pattern admits a trailing dot, so `Actions.` would otherwise be a
    different token from `actions`. The dot is stripped when it is the last character;
    interior dots (`node.js`) are untouched.
    """
    tokens: list[str] = []
    seen: set[str] = set()
    for match in LATIN_TOKEN_RE.finditer(text or ""):
        token = match.group(0).lower().rstrip(".")
        if len(token) < 2 or token in STOPLIST or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tokens


def token_set(text: str) -> set[str]:
    """Lesson text as a token set, using the same pattern and stoplist as the query side."""
    return set(latin_tokens(text))


def cjk_bigrams(text: str) -> set[str]:
    """Adjacent pairs inside each CJK run — the auxiliary channel, not the hypothesis."""
    grams: set[str] = set()
    for run in CJK_RUN_RE.findall(text or ""):
        grams.update(run[i : i + 2] for i in range(len(run) - 1))
    return grams


def explained_by_latin(wrong_hit: str | None, wrong_has: Iterable[str]) -> bool:
    """Broad reading: a top-1 lesson exists and holds at least one query Latin token."""
    return bool(wrong_hit) and bool(list(wrong_has))


def explained_strict(
    wrong_hit: str | None, wrong_has: Iterable[str], target_has: Iterable[str]
) -> bool:
    """Strict reading: the top-1 holds strictly more query tokens than the target does."""
    wrong_count = len(list(wrong_has))
    return explained_by_latin(wrong_hit, wrong_has) and wrong_count > len(list(target_has))


# ── input loading, with contract checks instead of KeyError archaeology ────────────────────────


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AnalysisError(f"missing input: {path}") from exc
    except json.JSONDecodeError as exc:
        raise AnalysisError(f"not valid JSON: {path}: {exc}") from exc


def load_probe(path: Path) -> list[dict[str, Any]]:
    data = read_json(path)
    if not isinstance(data, list) or not data:
        raise AnalysisError(f"{path}: expected a non-empty JSON array of probe rows")
    required = {"lesson_id", "target_lang", "overlap", "query", "ids", "rank", "ok"}
    for index, row in enumerate(data):
        if not isinstance(row, dict):
            raise AnalysisError(f"{path}: row {index} is not an object")
        missing = required - row.keys()
        if missing:
            raise AnalysisError(f"{path}: row {index} is missing {sorted(missing)}")
        if not isinstance(row["ids"], list):
            raise AnalysisError(f"{path}: row {index} has a non-list `ids`")
    return data


def load_corpus(path: Path) -> dict[str, dict[str, Any]]:
    data = read_json(path)
    if not isinstance(data, list) or not data:
        raise AnalysisError(f"{path}: expected a non-empty JSON array of lessons")
    corpus: dict[str, dict[str, Any]] = {}
    for index, lesson in enumerate(data):
        if not isinstance(lesson, dict):
            raise AnalysisError(f"{path}: lesson {index} is not an object")
        lesson_id = lesson.get("id")
        if not isinstance(lesson_id, str) or not lesson_id:
            raise AnalysisError(f"{path}: lesson {index} has no string `id`")
        if not isinstance(lesson.get("text"), str):
            raise AnalysisError(f"{path}: lesson {lesson_id!r} has no string `text`")
        if lesson_id in corpus:
            raise AnalysisError(f"{path}: duplicate lesson id {lesson_id!r}")
        corpus[lesson_id] = lesson
    return corpus


def load_zh_queries(path: Path) -> dict[str, dict[str, Any]]:
    data = read_json(path)
    if not isinstance(data, list):
        raise AnalysisError(f"{path}: expected a JSON array of queries")
    queries: dict[str, dict[str, Any]] = {}
    for query in data:
        if not (isinstance(query, dict) and query.get("lang") == "zh" and query.get("lesson_id")):
            continue
        lesson_id = str(query["lesson_id"])
        if lesson_id in queries and queries[lesson_id].get("query") != query.get("query"):
            raise AnalysisError(
                f"{path}: lesson_id {lesson_id!r} appears twice with different query text; "
                "the probe join on lesson_id would be ambiguous"
            )
        queries[lesson_id] = query
    return queries


def check_join(
    probe_rows: Iterable[dict[str, Any]], zh_queries: dict[str, dict[str, Any]]
) -> list[str]:
    """The probe is allegedly the Chinese subset of queries.json; verify, do not assume."""
    issues: list[str] = []
    for index, row in enumerate(probe_rows):
        lesson_id = row["lesson_id"]
        meta = zh_queries.get(lesson_id)
        if meta is None:
            issues.append(f"row {index}: {lesson_id} is not in the lang=zh query subset")
            continue
        if meta.get("query") != row["query"]:
            issues.append(f"row {index}: {lesson_id} query text differs from queries.json")
        if meta.get("overlap_bucket") not in (None, row["overlap"]):
            issues.append(
                f"row {index}: {lesson_id} overlap {row['overlap']!r} differs from "
                f"queries.json {meta['overlap_bucket']!r}"
            )
    return issues


def corpus_document_frequency(corpus: dict[str, dict[str, Any]]) -> Counter[str]:
    """How many of the 649 lessons contain each Latin token; context for a shared token."""
    frequency: Counter[str] = Counter()
    for lesson in corpus.values():
        frequency.update(token_set(lesson["text"]))
    return frequency


# ── one row ─────────────────────────────────────────────────────────────────────────────────


def bucket_of(row: dict[str, Any]) -> str:
    return f"{row['target_lang']}/{row['overlap']}"


def analyze_row(
    row: dict[str, Any],
    corpus: dict[str, dict[str, Any]],
    document_frequency: Counter[str] | None = None,
    query_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute the per-row evidence, keeping hits and both kinds of miss distinguishable."""
    document_frequency = document_frequency or Counter()
    query = row["query"]
    tokens = latin_tokens(query)
    target = corpus.get(row["lesson_id"])
    target_text = target["text"] if target else ""
    target_tokens = token_set(target_text)
    target_has = [token for token in tokens if token in target_tokens]

    ids = list(row["ids"])
    rank = row["rank"]
    # A hit's first id is the target, not a wrong hit. Only a rank-null row with ids has one.
    wrong_hit = ids[0] if rank is None and ids else None
    wrong = corpus.get(wrong_hit) if wrong_hit else None
    wrong_tokens = token_set(wrong["text"]) if wrong else set()
    wrong_has = [token for token in tokens if token in wrong_tokens]

    if rank is not None:
        miss_kind = "hit"
    elif wrong_hit:
        miss_kind = "wrong_hit"
    else:
        miss_kind = "no_hit"

    query_bigrams = cjk_bigrams(query)
    return {
        "lesson_id": row["lesson_id"],
        "target_lang": row["target_lang"],
        "overlap": row["overlap"],
        "bucket": bucket_of(row),
        "domain": (query_meta or {}).get("domain") or (target or {}).get("domain"),
        "query": query,
        "rank": rank,
        "miss_kind": miss_kind,
        "no_match": row.get("no_match"),
        "source": row.get("source"),
        "ids": ids,
        "latin_tokens": tokens,
        "latin_token_count": len(tokens),
        "token_document_frequency": {token: document_frequency.get(token, 0) for token in tokens},
        "target_in_corpus": target is not None,
        "target_has": target_has,
        "target_has_count": len(target_has),
        "target_has_cjk": bool(CJK_RUN_RE.search(target_text)),
        "wrong_hit": wrong_hit,
        "wrong_hit_in_corpus": wrong is not None,
        "wrong_has": wrong_has,
        "wrong_has_count": len(wrong_has),
        "explained_by_latin": explained_by_latin(wrong_hit, wrong_has),
        "explained_strict": explained_strict(wrong_hit, wrong_has, target_has),
        # Auxiliary, not part of the Latin verdict: could Chinese inside the lesson bridge it?
        "target_cjk_bigram_overlap": len(query_bigrams & cjk_bigrams(target_text)),
        "wrong_cjk_bigram_overlap": (
            len(query_bigrams & cjk_bigrams(wrong["text"])) if wrong else 0
        ),
    }


# ── aggregation: same counters for the four buckets, the languages, and the total ─────────────


def empty_counts() -> dict[str, int]:
    return {
        "queries": 0,
        "hits": 0,
        "misses": 0,
        "wrong_hit_misses": 0,
        "no_hit_misses": 0,
        "queries_with_latin_tokens": 0,
        "hits_with_latin_tokens": 0,
        "misses_with_latin_tokens": 0,
        "explained_by_latin": 0,
        "explained_strict": 0,
    }


def add_row(counts: dict[str, int], row: dict[str, Any]) -> None:
    counts["queries"] += 1
    has_latin = bool(row["latin_tokens"])
    if has_latin:
        counts["queries_with_latin_tokens"] += 1

    if row["miss_kind"] == "hit":
        counts["hits"] += 1
        if has_latin:
            counts["hits_with_latin_tokens"] += 1
        return

    counts["misses"] += 1
    if row["miss_kind"] == "wrong_hit":
        counts["wrong_hit_misses"] += 1
    else:
        counts["no_hit_misses"] += 1
    if has_latin:
        counts["misses_with_latin_tokens"] += 1
    if row["explained_by_latin"]:
        counts["explained_by_latin"] += 1
    if row["explained_strict"]:
        counts["explained_strict"] += 1


def aggregate(
    rows: Iterable[dict[str, Any]],
    key: Callable[[dict[str, Any]], str] | None = None,
) -> dict[str, dict[str, int]]:
    """Group rows by `bucket` (default) or any key, seeding the four canonical buckets."""
    if key is None:
        groups = {f"{lang}/{overlap}": empty_counts() for lang, overlap in CANONICAL_BUCKETS}
        key_func: Callable[[dict[str, Any]], str] = bucket_of
    else:
        groups = {}
        key_func = key
    for row in rows:
        name = key_func(row)
        counts = groups.setdefault(name, empty_counts())
        add_row(counts, row)
    return groups


def sum_counts(groups: Iterable[dict[str, int]]) -> dict[str, int]:
    total = empty_counts()
    for counts in groups:
        for field in total:
            total[field] += counts[field]
    return total


def source_breakdown(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Observational only: which misses did and did not run the semantic fallback."""
    groups: dict[str, dict[str, int]] = {}
    for row in rows:
        source = str(row.get("source") or "unknown")
        counts = groups.setdefault(
            source,
            {"queries": 0, "hits": 0, "misses": 0, "wrong_hit_misses": 0, "no_hit_misses": 0},
        )
        counts["queries"] += 1
        if row["miss_kind"] == "hit":
            counts["hits"] += 1
        else:
            counts["misses"] += 1
            if row["miss_kind"] == "wrong_hit":
                counts["wrong_hit_misses"] += 1
            else:
                counts["no_hit_misses"] += 1
    return groups


def top_latin_tokens_in_misses(
    rows: Iterable[dict[str, Any]], document_frequency: Counter[str], corpus_size: int
) -> list[dict[str, Any]]:
    """Frequency alone, plus document frequency: are the shared tokens technical or generic?"""
    miss_rows = [row for row in rows if row["miss_kind"] != "hit"]
    counts: Counter[str] = Counter()
    for row in miss_rows:
        counts.update(row["latin_tokens"])

    ranked = []
    for token, miss_queries in counts.items():
        ranked.append(
            {
                "token": token,
                "miss_queries": miss_queries,
                "in_wrong_hit": sum(1 for row in miss_rows if token in row["wrong_has"]),
                "in_target": sum(1 for row in miss_rows if token in row["target_has"]),
                "document_frequency": document_frequency.get(token, 0),
                "corpus_lessons": corpus_size,
            }
        )
    ranked.sort(
        key=lambda item: (-item["miss_queries"], -item["document_frequency"], item["token"])
    )
    return ranked


# ── the run ─────────────────────────────────────────────────────────────────────────────────


def definitions() -> dict[str, Any]:
    return {
        "latin_token_pattern": LATIN_TOKEN_PATTERN,
        "latin_token": (
            "maximal regex match, lowercased, deduplicated per query; dots, hyphens, '+' "
            "and '#' stay inside the token (node.js, docker-compose, c++, c#); a trailing "
            "sentence-final '.' is stripped"
        ),
        "stoplist": sorted(STOPLIST),
        "stoplist_rule": (
            "twelve pure-English function words removed before counting; technical "
            "abbreviations (ai, ci, pr, api, ...) are deliberately kept"
        ),
        "token_presence": (
            "a query token is present when the lesson text, tokenized with the same pattern "
            "and stoplist, contains the same whole token; substring hits (ai in 'said') are "
            "not counted"
        ),
        "explained_by_latin": (
            "miss with a top-1 lesson and at least one query Latin token present in that lesson"
        ),
        "explained_strict": (
            "broad case plus the top-1 holds strictly more query Latin tokens than the target"
        ),
        "bucket": "{target_lang}/{overlap}; every probe query is Chinese, so target_lang=en "
        "is the cross-lingual bucket and zh is same-language",
        "target_lang": (
            "the probe's own heuristic (CJK ratio > 0.25 in the first 1500 body characters), "
            "used as given; it describes the lesson's opening language, not the whole file, "
            "and many English-primary lessons still contain some CJK"
        ),
        "overlap": "the probe's own overlap field (high|low), not recomputed here",
        "corpus": "embed-ab/corpus.json snapshot; the live index may tokenize fields differently",
        "caveat": "many snapshot lessons contain CJK (see "
        "auxiliary.corpus_lessons_with_cjk), so 'cross-lingual' describes the target's "
        "primary language, not the absence of Chinese text",
    }


def summarize(
    probe_rows: list[dict[str, Any]],
    usable_rows: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    corpus: dict[str, dict[str, Any]],
    document_frequency: Counter[str],
    cache_dir: Path,
    zh_queries: dict[str, dict[str, Any]],
    join_issues: list[str],
) -> dict[str, Any]:
    buckets = aggregate(rows)
    by_language = aggregate(rows, key=lambda row: str(row["target_lang"]))
    totals = sum_counts(buckets.values())
    wrong_hit_misses = [row for row in rows if row["miss_kind"] == "wrong_hit"]

    def language_counts(language: str) -> dict[str, int]:
        return by_language.get(language, empty_counts())

    en = language_counts("en")
    zh = language_counts("zh")
    excluded = [
        describe_excluded(row, index)
        for index, row in enumerate(probe_rows)
        if row.get("ok") is not True
    ]

    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "inputs": {
            "cache_dir": str(cache_dir),
            "probe": str(cache_dir / PROBE_NAME),
            "corpus": str(cache_dir / CORPUS_REL),
            "queries": str(cache_dir / QUERIES_REL),
            "probe_rows": len(probe_rows),
            "usable_rows": len(usable_rows),
            "excluded_rows": len(excluded),
            "corpus_lessons": len(corpus),
            "zh_query_rows_joined": sum(1 for row in probe_rows if row["lesson_id"] in zh_queries),
            "join_issues": join_issues,
        },
        "definitions": definitions(),
        "headline": {
            "misses": totals["misses"],
            "misses_with_wrong_hit": totals["wrong_hit_misses"],
            "misses_with_no_hit": totals["no_hit_misses"],
            "misses_without_any_latin_token": (
                totals["misses"] - totals["misses_with_latin_tokens"]
            ),
            "explained_by_latin": totals["explained_by_latin"],
            "explained_strict": totals["explained_strict"],
            "cross_lingual": {
                "misses": en["misses"],
                "wrong_hit_misses": en["wrong_hit_misses"],
                "no_hit_misses": en["no_hit_misses"],
                "misses_with_latin_tokens": en["misses_with_latin_tokens"],
                "explained_by_latin": en["explained_by_latin"],
                "explained_strict": en["explained_strict"],
            },
            "same_language": {
                "misses": zh["misses"],
                "wrong_hit_misses": zh["wrong_hit_misses"],
                "no_hit_misses": zh["no_hit_misses"],
                "misses_with_latin_tokens": zh["misses_with_latin_tokens"],
                "explained_by_latin": zh["explained_by_latin"],
                "explained_strict": zh["explained_strict"],
            },
        },
        "totals": totals,
        "buckets": buckets,
        "by_target_lang": by_language,
        "by_source": source_breakdown(rows),
        "top_latin_tokens_in_misses": top_latin_tokens_in_misses(
            rows, document_frequency, len(corpus)
        ),
        "auxiliary": {
            "corpus_lessons_with_cjk": sum(
                1 for lesson in corpus.values() if CJK_RUN_RE.search(lesson["text"])
            ),
            "cross_lingual_rows_whose_target_has_cjk": sum(
                1 for row in rows if row["target_lang"] == "en" and row["target_has_cjk"]
            ),
            "wrong_hit_misses_sharing_a_cjk_bigram_with_top1": sum(
                1 for row in wrong_hit_misses if row["wrong_cjk_bigram_overlap"] > 0
            ),
            "wrong_hit_misses_where_top1_shares_more_cjk_bigrams_than_target": sum(
                1
                for row in wrong_hit_misses
                if row["wrong_cjk_bigram_overlap"] > row["target_cjk_bigram_overlap"]
            ),
            "targets_absent_from_corpus": sum(1 for row in rows if not row["target_in_corpus"]),
            "wrong_hits_absent_from_corpus": sum(
                1 for row in wrong_hit_misses if not row["wrong_hit_in_corpus"]
            ),
        },
        "excluded": excluded,
        "rows": rows,
    }


def describe_excluded(row: dict[str, Any], index: int) -> dict[str, Any]:
    reasons = []
    if row.get("curl_rc") not in (None, 0):
        reasons.append(f"curl rc={row['curl_rc']}")
    error = str(row.get("curl_err") or "").strip()
    if error:
        reasons.append(error)
    if not reasons:
        reasons.append("ok=false")
    return {
        "probe_index": index,
        "lesson_id": row["lesson_id"],
        "target_lang": row["target_lang"],
        "overlap": row["overlap"],
        "query": row["query"],
        "reason": "; ".join(reasons),
    }


def run(cache_dir: Path) -> dict[str, Any]:
    probe_rows = load_probe(cache_dir / PROBE_NAME)
    corpus = load_corpus(cache_dir / CORPUS_REL)
    zh_queries = load_zh_queries(cache_dir / QUERIES_REL)
    join_issues = check_join(probe_rows, zh_queries)

    usable_rows = [row for row in probe_rows if row.get("ok") is True]
    if not usable_rows:
        raise AnalysisError(f"{cache_dir / PROBE_NAME}: no row has ok=true")
    document_frequency = corpus_document_frequency(corpus)
    rows = [
        analyze_row(row, corpus, document_frequency, zh_queries.get(row["lesson_id"]))
        for row in usable_rows
    ]
    return summarize(
        probe_rows,
        usable_rows,
        rows,
        corpus,
        document_frequency,
        cache_dir,
        zh_queries,
        join_issues,
    )


# ── output ──────────────────────────────────────────────────────────────────────────────────


def _short(value: str | None, width: int = 36) -> str:
    if not value:
        return "-"
    return value if len(value) <= width else value[: width - 3] + "..."


def render(summary: dict[str, Any]) -> str:
    totals = summary["totals"]
    lines = [
        "Chinese-query retrieval: is a Latin token the reason for the miss?",
        f"probe rows {summary['inputs']['probe_rows']} · usable {totals['queries']} · "
        f"excluded {summary['inputs']['excluded_rows']}",
    ]
    for excluded in summary["excluded"]:
        lines.append(
            f"  excluded row {excluded['probe_index']}: {excluded['lesson_id']} — "
            f"{excluded['reason']}"
        )
    lines.extend(
        [
            f"latin token = {LATIN_TOKEN_PATTERN} "
            "(lowercased, deduplicated, trailing '.' stripped)",
            "stoplist = " + ", ".join(sorted(STOPLIST)),
            "presence = whole-token match against corpus.json text, not substring",
            "",
            f"{'bucket':<9}{'queries':>8}{'hits':>6}{'misses':>8}{'wrong-hit':>10}"
            f"{'no-hit':>8}{'latin q':>9}{'miss+lat':>10}{'explained':>11}{'strict':>8}",
        ]
    )

    def table_row(name: str, counts: dict[str, int]) -> str:
        return (
            f"{name:<9}{counts['queries']:>8}{counts['hits']:>6}{counts['misses']:>8}"
            f"{counts['wrong_hit_misses']:>10}{counts['no_hit_misses']:>8}"
            f"{counts['queries_with_latin_tokens']:>9}{counts['misses_with_latin_tokens']:>10}"
            f"{counts['explained_by_latin']:>11}{counts['explained_strict']:>8}"
        )

    for name, counts in summary["buckets"].items():
        lines.append(table_row(name, counts))
    lines.append(table_row("ALL", totals))

    headline = summary["headline"]
    en = headline["cross_lingual"]
    zh = headline["same_language"]
    lines.extend(
        [
            "",
            f"cross-lingual (target en): {en['misses']} misses "
            f"({en['wrong_hit_misses']} wrong-hit, {en['no_hit_misses']} no-hit) — "
            f"{en['explained_by_latin']} explained broad, {en['explained_strict']} strict",
            f"same-language (target zh): {zh['misses']} misses "
            f"({zh['wrong_hit_misses']} wrong-hit, {zh['no_hit_misses']} no-hit) — "
            f"{zh['explained_by_latin']} explained broad, {zh['explained_strict']} strict",
            f"{headline['misses_without_any_latin_token']} of {headline['misses']} misses "
            "contain no Latin token at all",
            "",
            "queries with a Latin token: "
            f"{totals['queries_with_latin_tokens']}/{totals['queries']} "
            f"(hit {totals['hits_with_latin_tokens']}/{totals['queries_with_latin_tokens']}) vs "
            f"{totals['hits'] - totals['hits_with_latin_tokens']}/"
            f"{totals['queries'] - totals['queries_with_latin_tokens']} without one",
        ]
    )

    explained_rows = [
        row for row in summary["rows"] if row["miss_kind"] == "wrong_hit" and row["latin_tokens"]
    ]
    if explained_rows:
        lines.extend(
            [
                "",
                "misses that carry a query Latin token:",
                f"  {'bucket':<9}{'tokens':<18}{'target has':<18}{'top-1':<38}"
                f"{'top-1 has':<16}{'explained':<11}strict",
            ]
        )
        for row in explained_rows:
            tokens = ",".join(row["latin_tokens"])
            target_has = ",".join(row["target_has"]) or "-"
            wrong_has = ",".join(row["wrong_has"]) or "-"
            lines.append(
                f"  {row['bucket']:<9}{_short(tokens, 16):<18}{_short(target_has, 16):<18}"
                f"{_short(row['wrong_hit'], 36):<38}{_short(wrong_has, 14):<16}"
                f"{('yes' if row['explained_by_latin'] else 'no'):<11}"
                f"{'yes' if row['explained_strict'] else 'no'}"
            )

    tokens = summary["top_latin_tokens_in_misses"]
    if tokens:
        lines.extend(["", "query Latin tokens among misses:"])
        for item in tokens:
            lines.append(
                f"  {item['token']:<18} {item['miss_queries']} miss quer"
                f"{'y' if item['miss_queries'] == 1 else 'ies'}, "
                f"document frequency {item['document_frequency']}/{item['corpus_lessons']}, "
                f"in {item['in_wrong_hit']} top-1 / {item['in_target']} target"
            )

    wrong_sources = summary["by_source"]
    without_semantic = sum(
        counts["wrong_hit_misses"]
        for source, counts in wrong_sources.items()
        if source == "worker-bm25"
    )
    lines.extend(
        [
            "",
            f"wrong-hit misses that never ran semantic (source=worker-bm25): "
            f"{without_semantic}/{headline['misses_with_wrong_hit']}",
            "auxiliary: "
            f"{summary['auxiliary']['corpus_lessons_with_cjk']}/"
            f"{summary['inputs']['corpus_lessons']} corpus lessons contain CJK; "
            f"{summary['auxiliary']['wrong_hit_misses_sharing_a_cjk_bigram_with_top1']} "
            f"of {headline['misses_with_wrong_hit']} wrong hits share a CJK bigram with the query",
        ]
    )
    return "\n".join(lines)


def default_cache_dir() -> Path:
    """MISAKANET_CACHE_DIR, else this checkout's .cache, else the main worktree's .cache."""
    override = os.environ.get("MISAKANET_CACHE_DIR")
    if override:
        return Path(override).expanduser()
    return cache_dir_for(Path(__file__).resolve().parents[1])


def cache_dir_for(repo_root: Path) -> Path:
    """Resolve `.cache` for a checkout; a linked worktree follows its gitdir to the main one."""
    direct = repo_root / ".cache"
    if (direct / PROBE_NAME).is_file():
        return direct

    gitfile = repo_root / ".git"
    if gitfile.is_file():
        marker = "gitdir:"
        text = gitfile.read_text(encoding="utf-8").strip()
        if text.startswith(marker):
            target = Path(text[len(marker) :].strip())
            if not target.is_absolute():
                target = (repo_root / target).resolve()
            # <main>/.git/worktrees/<name> → <main>
            if target.parent.name == "worktrees" and target.parent.parent.name == ".git":
                main_cache = target.parent.parent.parent / ".cache"
                if (main_cache / PROBE_NAME).is_file():
                    return main_cache
    return direct


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Quantify Latin-token matching in the Chinese-query retrieval probe."
    )
    parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help="cache directory holding zh-recall-probe-v2.json and embed-ab/ "
        "(default: MISAKANET_CACHE_DIR, else this checkout's .cache)",
    )
    parser.add_argument("--json", action="store_true", help="print the machine summary to stdout")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="JSON destination (default: <cache>/embed-ab/latin-token-analysis.json)",
    )
    args = parser.parse_args(argv)

    cache_dir = args.dir.expanduser() if args.dir else default_cache_dir()
    try:
        summary = run(cache_dir)
    except AnalysisError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    output = args.output or (cache_dir / OUTPUT_REL)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(render(summary))
        print(f"\nwrote {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
