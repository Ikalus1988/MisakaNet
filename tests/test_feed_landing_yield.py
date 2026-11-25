#!/usr/bin/env python3
"""The homepage's five feed slots must be worth a stranger's attention.

`docs/index.html` renders `(feed.items || []).slice(0, LATEST_LIMIT)` — the first five entries of
`docs/data/feed.json` and nothing else. On 2026-10-23 three of those five were repository plumbing:

    chore(main): release 3.22.0
    chore(data): 市场在售版本更新 …
    chore: auto-update lessons.json …

Every one of them is true and timestamped, and none of them is a reason for a visitor to keep reading.
The file is a landing surface, so the newest-first order is not automatically the most useful order.

The fix is ordering, never filtering: other consumers read this file, so `items` stays complete and
field names/shapes are untouched — the release entries simply move behind the human ones, and the
relative order of the human entries (`feat`/`fix`/`perf`) is preserved exactly. `landing_items` is a
pure function and `is_release_bookkeeping` is a single predicate, so the classification is pinned here
instead of being re-derived by scattered `"chore" in title` tests in the renderer.

The degenerate case matters as much as the happy one: a feed where *everything* is a `chore` must
still render five entries (the original order), because an empty "recent" block reads as "nothing
happened" — a claim about the project made by an ordering bug.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

spec = importlib.util.spec_from_file_location("build_feed", REPO / "scripts" / "build_feed.py")
bf = importlib.util.module_from_spec(spec)
sys.modules["build_feed"] = bf
spec.loader.exec_module(bf)

ROUTINE_PREFIXES = ("chore", "build", "ci", "style", "test", "docs")


def pr(title: str, ts: str) -> dict:
    return {"type": "merged_pr", "title": title, "url": "https://example.test/pr", "timestamp": ts,
            "source": "github"}


def lesson(title: str, ts: str) -> dict:
    return {"type": "lesson", "title": title, "url": "https://example.test/lesson", "timestamp": ts,
            "domain": "retrieval", "source": "lessons"}


def challenge(title: str, ts: str) -> dict:
    return {"type": "challenge", "title": title, "url": "https://example.test/issue", "labels": [],
            "timestamp": ts, "source": "github"}


MIXED = [
    # the shape measured on the live feed: newest entries are plumbing
    pr("chore(main): release 3.22.0", "2026-10-23T09:00:00Z"),
    pr("chore(data): 市场在售版本更新 sync", "2026-10-23T08:00:00Z"),
    challenge("评测：谁的检索在中文长查询上不崩", "2026-10-23T07:00:00Z"),
    pr("chore: auto-update lessons.json from intake", "2026-10-23T06:00:00Z"),
    pr("fix(mcp): search returned an empty list instead of an error", "2026-10-22T12:00:00Z"),
    pr("feat(intake): file the report on the network, not in a local queue", "2026-10-22T11:00:00Z"),
    lesson("Chroma 冷启动比 BM25 慢 40 倍", "2026-10-22T10:00:00Z"),
    pr("perf(retrieval): rerank only the top 20 candidates", "2026-10-22T09:00:00Z"),
    pr("ci: pin the wrangler version", "2026-10-22T08:00:00Z"),
]


def is_routine(item: dict) -> bool:
    """The rule the test asserts against, written once for the assertions below."""
    return bf.is_release_bookkeeping(item)


# ── (a) the mixed feed leads with something a visitor can read ───────────────────────────────────
def test_first_five_of_a_mixed_feed_carry_no_routine_prefix():
    ordered = bf.landing_items(MIXED)
    head = ordered[:5]
    assert len(head) == 5, head
    offenders = [i["title"] for i in head if i["title"].lower().startswith(ROUTINE_PREFIXES)]
    assert not offenders, f"release plumbing is still on the landing page: {offenders}"
    assert not [i for i in head if is_routine(i)], head
    # and the promotion is real: the human entries in `head` used to be at indices 2, 4, 5, 6, 7
    assert [i["title"] for i in head] == [
        "评测：谁的检索在中文长查询上不崩",
        "fix(mcp): search returned an empty list instead of an error",
        "feat(intake): file the report on the network, not in a local queue",
        "Chroma 冷启动比 BM25 慢 40 倍",
        "perf(retrieval): rerank only the top 20 candidates",
    ], head


# ── (b) titles that never adopted a conventional prefix are demoted too ──────────────────────────
def test_release_and_auto_update_titles_are_pushed_back():
    items = [
        pr("Release 3.23.0", "2026-10-23T09:00:00Z"),
        pr("auto-update lessons.json", "2026-10-23T08:00:00Z"),
        pr("Auto update activity snapshot", "2026-10-23T07:00:00Z"),
        pr("feat(search): explain a zero-result answer", "2026-10-23T06:00:00Z"),
    ]
    for item in items[:3]:
        assert is_routine(item), item["title"]
    ordered = bf.landing_items(items)
    assert ordered[0]["title"] == "feat(search): explain a zero-result answer", ordered
    assert [i["title"] for i in ordered[1:]] == [
        "Release 3.23.0", "auto-update lessons.json", "Auto update activity snapshot",
    ], ordered

    # a human PR that merely *mentions* release work keeps its place: the markers are start-anchored,
    # not substring matches, so this cannot silently demote real fixes.
    mention = pr("fix: release notes dropped the 2.48.0 section", "2026-10-23T05:00:00Z")
    assert not is_routine(mention), mention["title"]
    assert bf.landing_items([pr("release 3.23.0", "2026-10-23T09:00:00Z"), mention])[0] is mention


# ── (c) an all-plumbing feed degrades to the original order, never to nothing ────────────────────
def test_all_routine_feed_degrades_to_the_original_order():
    items = [
        pr("chore(main): release 3.22.0", "2026-10-23T09:00:00Z"),
        pr("chore(data): 市场在售版本更新", "2026-10-23T08:00:00Z"),
        pr("ci: pin the wrangler version", "2026-10-23T07:00:00Z"),
        pr("docs: regenerate the changelog", "2026-10-23T06:00:00Z"),
        pr("test: cover the empty query", "2026-10-23T05:00:00Z"),
        pr("style: reformat the renderer", "2026-10-23T04:00:00Z"),
    ]
    ordered = bf.landing_items(items)
    assert ordered, "an all-routine feed must not come back empty"
    assert [i["title"] for i in ordered] == [i["title"] for i in items], ordered
    assert len(ordered[:5]) == 5

    # also the truly uninteresting input, for the same reason
    assert bf.landing_items([]) == []
    assert bf.landing_items([pr("chore: autoupdate", "2026-10-23T00:00:00Z")])[0]["title"] == "chore: autoupdate"


# ── (d) reordering is not dropping ───────────────────────────────────────────────────────────────
def test_item_count_never_shrinks():
    ordered = bf.landing_items(MIXED)
    assert len(ordered) == len(MIXED)
    assert sorted(i["title"] for i in ordered) == sorted(i["title"] for i in MIXED)
    # every item is still the *same dict* — no field was renamed, dropped or rewritten
    assert all(any(i is original for original in MIXED) for i in ordered)
    for original in MIXED:
        assert any(i is original for i in ordered), original


def test_build_feed_keeps_every_item_and_leads_with_a_human_one(monkeypatch):
    """The wiring, not just the predicate: `build_feed` counts and ships everything it promoted."""
    monkeypatch.setattr(bf, "load_recent_lessons", lambda limit=5: [lesson("踩坑：缓存键没带版本", "2026-10-22T10:00:00Z")])
    monkeypatch.setattr(bf, "load_merged_prs", lambda limit=5: [
        pr("chore(main): release 3.22.0", "2026-10-23T09:00:00Z"),
        pr("feat(feed): lead with the human entries", "2026-10-23T08:00:00Z"),
    ])
    monkeypatch.setattr(bf, "load_challenges", lambda limit=5: [])

    feed = bf.build_feed()
    assert feed["item_count"] == 3 == len(feed["items"])
    # the newest human entry first, then the older one, then the plumbing — timestamp order survives
    # inside each group, so the promotion never invents a new chronology between human entries.
    assert [i["type"] for i in feed["items"]] == ["merged_pr", "lesson", "merged_pr"]
    assert feed["items"][0]["title"] == "feat(feed): lead with the human entries"
    assert feed["items"][1]["title"] == "踩坑：缓存键没带版本"
    assert feed["items"][2]["title"] == "chore(main): release 3.22.0"


# ── (e) the human entries keep their own relative order ─────────────────────────────────────────
def test_human_entries_keep_their_relative_order():
    ordered = bf.landing_items(MIXED)
    human_before = [i["title"] for i in MIXED if not is_routine(i)]
    human_after = [i["title"] for i in ordered if not is_routine(i)]
    assert human_after == human_before

    # explicitly: feat / fix / perf may not be reshuffled against each other
    kinds = [i["title"].split("(")[0] for i in ordered if i["title"].split("(")[0] in ("feat", "fix", "perf")]
    assert kinds == ["fix", "feat", "perf"], kinds


def test_the_feed_is_written_with_lf_not_the_platform_separator(tmp_path):
    """A Windows run must not commit a whole-file CRLF diff.

    `Path.write_text` translates `\n` to the platform separator, so before this was pinned a
    Windows regeneration produced a 136-line CRLF file — every line changed, the real change
    invisible. `tests/test_tracked_text_files_are_lf.py` is the gate that caught it (2026-11-25);
    this test catches it at the writer instead of at the commit.
    """
    target = bf.write_feed({"generated_at": "x", "item_count": 0, "items": []},
                                   tmp_path / "feed.json")
    raw = target.read_bytes()
    assert b"\r\n" not in raw, "the feed must be written with \n, never the platform separator"
    assert raw.endswith(b"\n")
