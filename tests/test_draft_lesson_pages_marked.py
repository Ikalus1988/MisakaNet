#!/usr/bin/env python3
"""A non-published lesson page must say so, on the page and in its meta description.

Measured 2026-10-04 against production: `https://misakanet.org/lessons/fanuc-alarm-code-reference/`
is a `draft` in `data/lessons.json`, is listed in `sitemap.xml`, and returned HTTP 200 — with **zero**
occurrences of "draft", "unpublished" or any equivalent. Its `<title>` and `<h1>` were identical to a
published lesson's.

The MCP side of the same corpus already got this right: #2423 made `status` visible on every hit, and
it is present exactly where it matters (verified live — a draft hit carries `status: "draft"`, a
published hit has no `status` key at all). This test pins the page half to the same rule, so the two
surfaces cannot drift apart again.

It deliberately does **not** assert that drafts are unpublished or unindexed. That is a product
decision (#2270 and the surrounding discussion); this only asserts that whatever is published is
*labelled*. A page that says "draft" is honest even if the decision about serving it is still open.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from build_lesson_pages import build_lesson_page, slugify  # noqa: E402  (after sys.path)

CORPUS = REPO / "data" / "lessons.json"
BANNER = '<div class="draft-banner"'


def lessons() -> list[dict]:
    return json.loads(CORPUS.read_text(encoding="utf-8"))


def page_for(lesson: dict) -> str:
    return build_lesson_page(lesson)


def test_the_corpus_actually_contains_both_cases():
    """A guard that never sees a draft cannot fail, which is the defect class this file exists to
    prevent (see #2270, where the original draft check read a field the search never returned)."""
    statuses = {r.get("status") or "published" for r in lessons()}
    assert "published" in statuses, "no published lessons — is the corpus shape still what we think?"
    assert statuses - {"published"}, f"no non-published lessons to guard: {sorted(statuses)}"


def test_every_non_published_lesson_page_carries_a_visible_draft_notice():
    non_published = [r for r in lessons() if (r.get("status") or "published") != "published"]
    missing = []
    for lesson in non_published:
        html = page_for(lesson)
        if BANNER not in html:
            missing.append(f"{lesson.get('title', '?')[:50]} (status={lesson.get('status')})")
        elif lesson["status"] not in html:
            missing.append(f"{lesson.get('title', '?')[:50]} — banner present but does not name the status")
    assert not missing, (
        "these non-published lessons render with no indication they are unfinished, while the MCP "
        f"response for the same lesson carries status: {missing}\n"
        "A reader or a crawler building a snippet cannot tell the difference."
    )


def test_the_notice_also_reaches_the_meta_description():
    """The description is what a search result shows. A banner on the page does not help the person
    who never clicks it."""
    for lesson in [r for r in lessons() if (r.get("status") or "published") != "published"]:
        html = page_for(lesson)
        meta = html.split('name="description"', 1)[-1].split(">", 1)[0]
        assert "Draft" in meta, (
            f"{lesson.get('title', '?')[:50]}: the meta description does not disclose the draft state"
        )


def test_published_pages_carry_no_draft_notice():
    """The other direction: a marker on settled content is its own kind of wrong."""
    published = [r for r in lessons() if (r.get("status") or "published") == "published"]
    for lesson in published[:40]:  # sample: rendering every page is slow and one is as good as another
        html = page_for(lesson)
        assert BANNER not in html, f"{lesson.get('title', '?')[:50]} is published but got a draft banner"
        meta = html.split('name="description"', 1)[-1].split(">", 1)[0]
        assert "Draft (not published)" not in meta, "a published lesson's description claims it is a draft"


def test_an_absent_status_defaults_to_published_rather_than_draft():
    """`status` is optional in the corpus. Treating a missing field as draft would put a banner on
    every lesson that predates the field — the same false-signal failure, inverted."""
    html = build_lesson_page({"title": "No status field", "domain": "test", "summary": "s"})
    assert BANNER not in html
    html = build_lesson_page({"title": "Draft status", "domain": "test", "summary": "s", "status": "draft"})
    assert BANNER in html
    # And an unknown non-published status must still be labelled, not silently treated as published.
    for other in ("active", "review", "deprecated"):
        html = build_lesson_page({"title": "Odd status", "domain": "test", "summary": "s", "status": other})
        assert BANNER in html, f"status={other!r} rendered with no notice"
        assert other in html, f"status={other!r} — the notice does not name the actual status"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            print(f"  {name} ... ", end="", flush=True)
            try:
                fn()
                print("PASS")
            except Exception as e:
                print(f"FAIL: {e}")
