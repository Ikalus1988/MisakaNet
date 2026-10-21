#!/usr/bin/env python3
"""The pixel comparison must be able to see the pages the generator writes.

`scripts/compare_site_pixels.py` answers one question: *did this change move anything on screen?*
Its page set decides what it can answer. The set used to be the 14 hand-written pages only, and
that was right while the generated tree was 571 pages of hardcoded palette with no footer — there
was nothing to compare, because the design gate did not read them either (handoff §122.6 item 2).

That is no longer true. The generated tree is in the design gate, it is what `main` and `dist`
publish, and it is what a reader lands on. A change to `scripts/build_lesson_pages.py` now moves
571 pages, and a rendering check that cannot see one of them cannot answer whether it did.

Capturing all 571 at three viewports is tens of minutes and hundreds of megabytes, so the set
stays small — and the unit that makes it safe to keep small is the **template**: all 516 lesson
pages come from `HTML_TEMPLATE`, all 54 topic pages from `TOPIC_TEMPLATE`, and the topic index
from `TOPICS_INDEX_TEMPLATE`. A structural change to a template lands on every page it produces,
so one page per template covers the tree.

The controls matter as much as the claims: a set that silently collapsed to the hand-written pages
again would pass every assertion here except the one that says the generated pages are in it.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import compare_site_pixels as cpx  # noqa: E402

DOCS = REPO / "docs"


def _parts(page: Path) -> set[str]:
    return set(page.relative_to(DOCS).parts)


def _is_topic_page(page: Path) -> bool:
    """A topic page, as opposed to the topic index.

    Every page in the tree is named `index.html` — the URLs are directory-style
    (`/topics/agent/`) — so the index and a topic page are told apart by *depth*, not by name:
    the index sits directly in `docs/topics/`, a topic page one directory deeper.
    """
    parts = page.relative_to(DOCS).parts
    return parts[0] == "topics" and len(parts) > 2


def _is_topic_index(page: Path) -> bool:
    return page.relative_to(DOCS).parts == ("topics", "index.html")


def test_the_default_set_covers_every_hand_written_page():
    hand = cpx.hand_written_pages(DOCS)
    default = cpx.default_pages(DOCS)
    assert hand, "the repo has hand-written pages; an empty partition means the rule broke"
    missing = [p for p in hand if p not in default]
    assert not missing, f"the default set dropped hand-written pages: {missing[:3]}"


def test_the_default_set_reaches_the_generated_tree():
    """One page per generator template — the three that exist."""
    default = cpx.default_pages(DOCS)
    lessons = [p for p in default if "lessons" in _parts(p)]
    topics = [p for p in default if _is_topic_page(p)]
    index = [p for p in default if _is_topic_index(p)]

    assert lessons, "no lesson page in the default set: a change to HTML_TEMPLATE would be invisible"
    assert topics, "no topic page in the default set: a change to TOPIC_TEMPLATE would be invisible"
    assert index, "the topic index is missing: a change to TOPICS_INDEX_TEMPLATE would be invisible"


def test_the_default_set_stays_small():
    """The point of sampling per template is that the set is small enough to always capture."""
    default = cpx.default_pages(DOCS)
    generated_total = len(list((DOCS / "lessons").rglob("*.html"))) + len(
        list((DOCS / "topics").rglob("*.html"))
    )
    assert len(default) < generated_total, (
        f"the default set is as big as the generated tree ({len(default)} pages) — "
        "then it is not a sample, it is the whole tree"
    )
    assert len(default) <= 25, f"the default set grew to {len(default)} pages; that is not a sample"


def test_every_page_in_the_default_set_exists():
    for page in cpx.default_pages(DOCS):
        assert page.exists(), f"the default set names a page that is not there: {page}"


def test_the_default_set_is_deterministic():
    """Two captures must pick the same pages, or a before/after comparison is not comparable."""
    assert cpx.default_pages(DOCS) == cpx.default_pages(DOCS)


def test_naming_a_page_still_reaches_any_page_in_the_tree():
    """`--pages` is the escape hatch: it must still be able to name any generated page."""
    selectable = cpx.selectable_pages(DOCS)
    hand = set(cpx.hand_written_pages(DOCS))
    generated = [p for p in selectable if p not in hand]
    assert len(generated) > 500, f"only {len(generated)} generated pages are selectable"
    lessons = [p for p in generated if "lessons" in _parts(p)]
    assert lessons, "no lesson page is selectable by name"
