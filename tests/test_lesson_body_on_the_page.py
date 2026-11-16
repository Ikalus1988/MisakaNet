#!/usr/bin/env python3
"""The lesson's own text has to reach the page, and nothing else may.

Why this exists (2026-11-16)
----------------------------
Every generated lesson page used to render the title, the evidence level, the tags and **one
paragraph of `summary`** — about 50 words. Measured on the generated tree: 909 published pages, so
the 988-lesson corpus that makes the site worth visiting was the one part of it a crawler could not
read. Search Console named the consequence before anyone measured anything: soft 404 and "duplicate,
Google chose a different canonical" arrived together, which is the signature of 909 near-identical
shells.

Two halves are pinned here, and they pull in opposite directions on purpose:

* **the body is there** — every published lesson page carries text from its own markdown, not only
  the summary. A page that stops carrying it would go back to being a shell, and nothing else in CI
  would notice: the page still generates, still returns 200, still has a canonical;
* **nothing but text is there** — the renderer escapes first and emits only its own tags, so a lesson
  that writes `<user>` or quotes `<div class="modal">` shows those characters instead of injecting
  them. 81 of the 988 lessons contain `<…>` in prose.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import lesson_markdown  # noqa: E402
from build_lesson_pages import build_lesson_page  # noqa: E402

CORPUS = REPO / "data" / "lessons.json"
BODY_OPEN = '<div class="lesson-body">'
BODY_RE = re.compile(r'<div class="lesson-body">(?P<body>[\s\S]*?)</div>')


def lessons() -> list[dict]:
    return json.loads(CORPUS.read_text(encoding="utf-8"))


def published() -> list[dict]:
    return [row for row in lessons() if (row.get("status") or "published") == "published"]


def page_path(lesson: dict) -> Path | None:
    """The generated page for a lesson, resolved the way the generator names directories."""
    from build_lesson_pages import slugify

    slug = lesson.get("_slug") or slugify(lesson.get("title", ""))
    return REPO / "docs" / "lessons" / slug / "index.html"


def markdown_body(lesson: dict) -> str:
    reference = lesson.get("url") or ""
    path = REPO / reference
    if not reference or not path.is_file():
        return ""
    return lesson_markdown.FRONTMATTER.sub("", path.read_text(encoding="utf-8"))


def body_region(html: str) -> str:
    match = BODY_RE.search(html)
    return match.group("body") if match else ""


# ── the body is on the page ─────────────────────────────────────────────────────────────────────
def test_the_generated_pages_carry_a_body_region():
    """The generator's own output, before anything touches disk."""
    missing = [row["id"] for row in published()[:40] if BODY_OPEN not in build_lesson_page(row)]
    assert not missing, f"these lessons render no body at all: {missing}"


def test_a_long_lesson_does_not_render_as_two_lines():
    """The defect, stated as a floor rather than as a word count.

    A lesson whose markdown runs to 2 KB must put at least 800 characters of it on the page. The
    summary is capped at 161 characters (`data/lessons.json`), so a page that only carries the
    summary fails this by construction — which is exactly the state the site shipped for months.
    """
    thin = []
    for row in published():
        text = markdown_body(row)
        if len(text) < 2000:
            continue
        rendered = body_region(build_lesson_page(row))
        if len(rendered) < 800:
            thin.append((row["id"], len(text), len(rendered)))
    assert not thin, (
        "these lessons have a long markdown body but a nearly empty page — the page is a shell again "
        f"(id, markdown chars, rendered chars): {thin[:10]}"
    )


def _plain_text(html: str) -> str:
    """What a reader sees: tags removed, entities resolved, whitespace collapsed."""
    import html as html_module

    return re.sub(r"\s+", " ", html_module.unescape(re.sub(r"<[^>]+>", " ", html)))


def test_the_page_quotes_markdown_that_the_summary_does_not():
    """Not just *some* text: a prose line that exists only in the lesson's own body.

    The line has to carry no markdown of its own (`*`, `` ` ``, `[`, `#`, a list marker), otherwise the
    check would be testing the renderer's inline rules rather than whether the body is on the page at
    all. One such line exists in nearly every lesson; the corpus is prose with code in it.
    """
    checked = 0
    for row in published():
        text = markdown_body(row)
        body = _plain_text(body_region(build_lesson_page(row)))
        if not body:
            continue
        line = next(
            (candidate.strip() for candidate in text.splitlines()
             if len(candidate.strip()) > 120
             and not lesson_markdown._starts_block(candidate)
             and not set(candidate) & set("*`[]#|>_")),
            "",
        )
        if not line:
            continue
        excerpt = line[:40]
        assert excerpt in body, (
            f"{row['id']}: its own prose line is not on the page: {excerpt!r}")
        checked += 1
        if checked >= 25:
            break
    assert checked >= 20, f"only {checked} lessons could be checked — the corpus shape changed"


def test_the_body_regions_on_disk_are_not_empty():
    """The committed tree, not just the generator: a stale `docs/` would pass every test above."""
    empty = []
    for row in published():
        path = page_path(row)
        if path is None or not path.is_file():
            continue
        if len(body_region(path.read_text(encoding="utf-8"))) < 40:
            empty.append(row["id"])
    assert not empty, f"these committed pages carry no lesson body: {empty[:10]}"


# ── nothing but text is on the page ────────────────────────────────────────────────────────────
def test_a_lesson_cannot_inject_markup():
    """Every `<` in a lesson reaches the page as `&lt;`; there is no passthrough to configure."""
    assert lesson_markdown.render("A tag <span>here</span> and a script <script>x()</script>.") == (
        "<p>A tag &lt;span&gt;here&lt;/span&gt; and a script &lt;script&gt;x()&lt;/script&gt;.</p>"
    )


def test_no_generated_page_carries_a_script_tag_from_a_lesson():
    offenders = [
        row["id"] for row in published()
        if "<script" in body_region(build_lesson_page(row)).lower()
    ]
    assert not offenders, f"a lesson body produced a <script>: {offenders[:5]}"


def test_a_javascript_url_never_becomes_an_href():
    """A lesson quotes `javascript:` as often as it describes it; only http(s) and site paths link."""
    html = lesson_markdown.render("[x](javascript:alert(1)) and [y](https://example.com/a)")
    assert "javascript:" in html  # shown as text
    assert 'href="javascript:' not in html
    assert 'href="https://example.com/a"' in html


# ── drafts ─────────────────────────────────────────────────────────────────────────────────────
def test_a_draft_page_is_noindex_and_a_published_one_is_not():
    """2026-11-16: `benchmark-honesty-simulated-vs-real` was a draft, is not in the sitemap, and URL
    Inspection reported "Submitted and indexed" — Google had found it through `/topics/agent/`.
    Sitemap omission is a request; `noindex` is the control.
    """
    pool = lessons()
    drafts = [row for row in pool if (row.get("status") or "published") != "published"]
    assert drafts, "no draft lessons in the corpus — this test would pass vacuously"
    for row in drafts:
        html = build_lesson_page(row)
        assert '<meta name="robots" content="noindex, follow">' in html, (
            f"{row['id']} is {row.get('status')} and can be indexed")
    for row in published()[:20]:
        assert "noindex" not in build_lesson_page(row), f"{row['id']} is published but noindex"


def test_the_committed_draft_pages_carry_the_same_noindex():
    drafts = [row for row in lessons() if (row.get("status") or "published") != "published"]
    stale = []
    for row in drafts:
        path = page_path(row)
        if path is None or not path.is_file():
            continue
        if "noindex" not in path.read_text(encoding="utf-8"):
            stale.append(row["id"])
    assert not stale, f"these committed draft pages are still indexable: {stale[:10]}"


@pytest.mark.parametrize("status", ["draft", "superseded", "active", "review"])
def test_an_unknown_non_published_status_is_noindex_too(status):
    """Fail-safe, the same way the draft banner is: an unrecognised status is not a search result."""
    html = build_lesson_page({"title": "x", "summary": "y", "status": status})
    assert "noindex" in html
