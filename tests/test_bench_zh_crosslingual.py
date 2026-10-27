#!/usr/bin/env python3
"""`scripts/bench_zh_crosslingual.py` — everything except the network.

Why a test for a probe script
-----------------------------
The script's job is to stop one specific mistake: reporting a single "Chinese recall" number that
averages a problem the CJK channel owns (a Chinese query aimed at a Chinese lesson) with one it
structurally cannot touch (a Chinese query aimed at an English lesson). Two ways this probe can lie,
and both are tested here because both are silent:

1. **Bucket a lesson by the wrong text.** `lesson_language` reads the body, not the frontmatter —
   every lesson's frontmatter tags are English, so counting them drags Chinese lessons under the
   threshold and files them as cross-lingual targets.
2. **Score a transport failure as a miss.** A dropped connection and a genuine `no_match` both have
   zero results, and the probe's first run did exactly this: 20 of 64 empty bodies, caused by a
   local `https_proxy`, would have read as a 31% recall disaster.

The third invariant is the one the report leans on: a miss that returned *something* is counted
separately from a miss that returned nothing, because only the second one ever reaches the semantic
fallback (`register-proxy-sw.js` runs it on an empty BM25 result and never re-ranks a hit).
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts import bench_zh_crosslingual as probe  # noqa: E402

ZH_LESSON = """---
title: 飞书 callout 写入静默丢内容
domain: feishu
tags:
- feishu
- callout
---

## Problem
向飞书文档的 callout 块写入含嵌套列表的 markdown 时，返回 success 但内容被清空。
"""

EN_LESSON = """---
title: 飞书 callout 写入静默丢内容
domain: feishu
tags:
- feishu
- callout
---

## Problem
Writing nested markdown lists into a Feishu callout returns success and empties the block.
"""


def write(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


# ── the two buckets have to be separated by the lesson's own body ───────────────────────────────────

def test_a_chinese_lesson_is_bucketed_as_zh(tmp_path):
    assert probe.lesson_language(write(tmp_path, "a.md", ZH_LESSON)) == "zh"


def test_an_english_lesson_is_bucketed_as_en_even_with_a_chinese_title(tmp_path):
    # The frontmatter is where a naive classifier goes wrong: identical Chinese title, English body.
    assert probe.lesson_language(write(tmp_path, "b.md", EN_LESSON)) == "en"


def test_a_missing_file_is_unknown_rather_than_silently_english(tmp_path):
    # Folding a broken path into `en` would quietly inflate the cross-lingual bucket.
    assert probe.lesson_language(tmp_path / "nope.md") == "unknown"


def test_cjk_ratio_counts_characters_not_bytes():
    assert probe.cjk_ratio("abc") == 0.0
    assert probe.cjk_ratio("中文") == 1.0
    assert probe.cjk_ratio("") == 0.0
    # Whitespace is not a character in the denominator: "中 a" is 1/2, not 1/3.
    assert probe.cjk_ratio("中 a") == 0.5


# ── the tally has to exclude transport failures and split misses by result shape ────────────────────

def rows() -> list[dict]:
    return [
        # zh target: one hit, one miss that returned a wrong lesson
        {"target_lang": "zh", "overlap": "high", "rank": 1, "ids": ["x"], "no_match": False, "source": "worker-bm25", "ok": True},
        {"target_lang": "zh", "overlap": "low", "rank": None, "ids": ["y"], "no_match": False, "source": "worker-bm25", "ok": True},
        # en target: one miss with no results at all (semantic ran and found nothing)
        {"target_lang": "en", "overlap": "high", "rank": None, "ids": [], "no_match": True, "source": "worker-bm25", "ok": True},
        # a dropped connection: must not enter any denominator
        {"target_lang": "en", "overlap": "low", "rank": None, "ok": False},
    ]


def test_transport_failures_never_enter_the_denominator():
    summary = probe.tally(rows())
    assert summary["transport_failures"] == 1
    assert summary["buckets"]["zh->zh"]["n"] == 2
    assert summary["buckets"]["zh->en"]["n"] == 1


def test_rates_are_computed_over_successful_rows_only():
    summary = probe.tally(rows())
    zh = summary["buckets"]["zh->zh"]
    assert zh["r@1"] == 0.5
    assert zh["r@5"] == 0.5
    assert zh["no_match"] == 0.0  # the miss returned a lesson; it just was not the target
    en = summary["buckets"]["zh->en"]
    assert en["r@1"] == 0.0
    assert en["no_match"] == 1.0


def test_a_miss_that_returned_something_is_separated_from_one_that_returned_nothing():
    summary = probe.tally(rows())
    assert summary["buckets"]["zh->zh"]["miss_with_results"] == 1
    assert summary["buckets"]["zh->en"]["miss_with_no_results"] == 1


def test_overlap_breakdown_is_reported_next_to_the_language_buckets():
    summary = probe.tally(rows())
    assert summary["buckets"]["zh->zh/high"]["n"] == 1
    # zh->en/low held only the dropped connection, so the bucket has no successful row and is
    # absent rather than present-with-zero — a zero would read as "measured, nothing worked".
    assert "zh->en/low" not in summary["buckets"]


def test_render_prints_the_headline_buckets_and_the_overlap_split():
    text = probe.render(probe.tally(rows()))
    assert "zh->zh" in text and "zh->en" in text
    assert "by overlap" in text
    assert "transport failures" in text


# ── the query set is read as published ─────────────────────────────────────────────────────────────

def test_the_published_query_set_carries_zh_rows_with_a_target():
    rows = probe.load_queries(REPO / "docs" / "benchmarks" / "retrieval-l1-267-queries.jsonl")
    assert rows, "the L1-267 query set should contain zh queries"
    assert all(r["lang"] == "zh" for r in rows)
    assert all(r["target_url"].startswith("lessons/") for r in rows)
    assert probe.load_queries(REPO / "docs" / "benchmarks" / "retrieval-l1-267-queries.jsonl", limit=3)
    assert len(probe.load_queries(REPO / "docs" / "benchmarks" / "retrieval-l1-267-queries.jsonl", limit=3)) == 3
