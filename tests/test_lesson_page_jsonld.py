#!/usr/bin/env python3
"""Every lesson page carries structured data — and it says only what the corpus can prove.

Measured 2026-11-26
-------------------
`application/ld+json` appeared **0 times** across 1,164 `/lessons/<slug>/` pages, while the
home page had one. The pages that are this repository's product were the only ones a crawler
had to describe for itself: a title, a canonical URL, a date and a paragraph of description,
all of it plain text.

That gap is what an external review called "the biggest incremental opportunity" — and the
review's own diagnosis was wrong (`scripts/build_lesson_pages.py` has always emitted these
pages); the real gap was one field. It is worth stating because it decided what this change
is: not a new page type, one `<script type="application/ld+json">` per lesson.

What this pins
--------------
1. **Every published page has exactly one block, and it parses.** Two blocks would be two
   claims; a malformed one is invisible to JSON-LD consumers and looks like coverage.
2. **It names the page it is on.** `headline`/`url` must be that lesson's, not a neighbour's —
   a copy-paste of the template is exactly how that drifts.
3. **The breadcrumb climbs Home → topic → lesson**, because that is the half with a visible
   SERP effect (a path instead of a raw URL).
4. **A datum the corpus does not have is absent, not invented.** `datePublished` only when
   `created` is a real `YYYY-MM-DD`; no `author`/`image`/`publisher.logo` at all (nothing in the
   published bundle supports them).
5. **A draft emits nothing** — it is `noindex`, and structured data on a page we ask crawlers
   not to index is decoration.
6. **A lesson title cannot end the data block.** `</script>` inside a title is the one injection
   that matters here, and it is cheap to prove.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

import build_lesson_pages as blp  # noqa: E402

BLOCK = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
# The page says whether it is a draft; that is the same signal a crawler gets, so the test does
# not need the slug map to decide (and a test that re-derives draft-ness could disagree with the
# page it is inspecting).
NOINDEX = re.compile(r'<meta name="robots" content="noindex')


def _pages() -> list[tuple[Path, str]]:
    """(path, page text) for every lesson page on disk — walked, not derived from the index."""
    return [(path, path.read_text(encoding="utf-8"))
            for path in sorted((REPO / "docs" / "lessons").glob("*/index.html"))]


def _published(page: str) -> bool:
    return not NOINDEX.search(page)


def _graph(page: str) -> dict:
    blocks = BLOCK.findall(page)
    assert len(blocks) == 1, f"{len(blocks)} JSON-LD block(s) on one page"
    return json.loads(blocks[0])


def test_every_published_page_has_one_parseable_block():
    checked, missing = 0, []
    for path, page in _pages():
        if not _published(page):
            continue
        checked += 1
        if not BLOCK.search(page):
            missing.append(path.parent.name)
            continue
        _graph(page)  # raises on malformed JSON
    assert checked > 1000, f"only {checked} published pages were inspected"
    assert not missing, f"{len(missing)} published page(s) carry no JSON-LD: {missing[:3]}"


def test_the_block_names_the_page_it_is_on():
    """`url` is the page's own canonical — a copy-paste of the template is how that drifts."""
    for path, page in _pages()[:120]:
        if not _published(page):
            continue
        graph = _graph(page)["@graph"]
        article = next(node for node in graph if node["@type"] == "TechArticle")
        expected = f"{blp.SITE_URL}/lessons/{path.parent.name}/"
        assert article["url"] == expected, f"{article['url']} != {expected}"
        assert article["mainEntityOfPage"]["@id"] == expected
        assert f'<link rel="canonical" href="{expected}">' in page, "canonical and JSON-LD disagree"


def test_the_breadcrumb_is_home_topic_lesson():
    for _path, page in _pages()[:40]:
        if not _published(page):
            continue
        graph = _graph(page)["@graph"]
        trail = next(node for node in graph if node["@type"] == "BreadcrumbList")
        items = trail["itemListElement"]
        assert [item["position"] for item in items] == [1, 2, 3]
        assert items[0]["item"] == f"{blp.SITE_URL}/"
        assert "/topics/" in items[1]["item"]
        article = next(node for node in graph if node["@type"] == "TechArticle")
        assert items[2]["item"] == article["url"]


def test_a_date_is_emitted_only_when_the_corpus_has_one():
    published = blp.lesson_json_ld(title="T", description="D", canonical="https://x/lessons/t/",
                                   domain="devops", tags=[], created="2026-10-25",
                                   updated="not-a-date")
    article = json.loads(BLOCK.findall(published)[0])["@graph"][0]
    assert article["datePublished"] == "2026-10-25"
    assert "dateModified" not in article, "a non-date was emitted as dateModified"

    undated = blp.lesson_json_ld(title="T", description="D", canonical="https://x/lessons/t/",
                                 domain="devops", tags=[])
    article = json.loads(BLOCK.findall(undated)[0])["@graph"][0]
    assert "datePublished" not in article and "dateModified" not in article


def test_nothing_is_claimed_that_the_bundle_cannot_support():
    """No `author`, `image` or `publisher.logo` — each would be a claim with no artifact."""
    page = blp.lesson_json_ld(title="T", description="D", canonical="https://x/lessons/t/",
                              domain="devops", tags=["a"])
    article = json.loads(BLOCK.findall(page)[0])["@graph"][0]
    for field in ("author", "image"):
        assert field not in article, f"{field} appeared without anything in the corpus behind it"
    assert "logo" not in article["publisher"]


def test_a_draft_page_emits_nothing():
    drafts = 0
    for path, page in _pages():
        if _published(page):
            continue
        drafts += 1
        assert not BLOCK.search(page), f"a noindex page carries structured data: {path.parent.name}"
    assert drafts > 10, f"only {drafts} draft page(s) found — the check inspected almost nothing"


def test_a_title_cannot_end_the_data_block():
    """The only injection that matters here: `</script>` inside a lesson title."""
    hostile = "Close </script><script>alert(1)</script> and continue"
    block = blp.lesson_json_ld(title=hostile, description="D", canonical="https://x/lessons/t/",
                              domain="devops", tags=[])
    assert block.count("</script>") == 1, "the data block was closed more than once"
    payload = BLOCK.findall(block)[0]
    assert json.loads(payload)["@graph"][0]["headline"] == hostile, (
        "escaping changed the value a parser reads — `\\/` must round-trip to `/`")
