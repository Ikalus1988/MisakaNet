#!/usr/bin/env python3
"""The front page has to work without a mouse and without motion.

Measured on `docs/index.html` on 2026-10-02, before this change: **0** `<h1>`, **0** `<main>`, **0**
`prefers-reduced-motion` rules — against 24 keyframes and `transition:` declarations — and **0**
`role="status"`/`aria-live` regions. The drawer was hidden with `left: -300px`, which moves it
off-canvas but leaves its links in the tab order, so a keyboard reader tabbed through invisible links
before reaching the page.

Each rule below is written against the failure it prevents, and each was mutation-checked by undoing
the corresponding edit in the page and watching this file go red.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PAGE = (REPO / "docs" / "index.html").read_text(encoding="utf-8")


def test_the_page_has_exactly_one_h1_and_it_is_the_site_title():
    """Headings used to start at `h3`; a screen reader's heading list had no entry point."""
    headings = re.findall(r"<h1\b[^>]*>", PAGE)
    assert len(headings) == 1, f"expected exactly one h1, found {len(headings)}: {headings}"
    assert 'data-i18n="siteTitle"' in headings[0], (
        "the h1 must be the site title, so the language switch keeps translating it")


def test_the_content_sits_in_a_main_landmark_and_the_footer_does_not():
    """`<main>` is what lets a reader skip the drawer and the header in one jump; a footer inside it
    is a common mistake that makes the landmark mean less."""
    assert "<main" in PAGE, "no main landmark"
    main_close = PAGE.index("</main>")
    footer = PAGE.index("<footer")
    assert footer > main_close, "the footer is inside <main>"
    assert PAGE.index("</header>") < PAGE.index("<main"), "the header is inside <main>"


def test_the_closed_drawer_is_not_in_the_tab_order():
    """`inert` (plus `aria-hidden`) is what takes the off-canvas links out of the tab order.

    The class alone only moves the drawer: `left: -300px` is still focusable, and every link inside
    it still answers Tab.
    """
    nav = re.search(r"<nav class=\"drawer\"[^>]*>", PAGE)
    assert nav, "the drawer markup moved; this test reads its opening tag"
    assert "inert" in nav.group(0), "the closed drawer is focusable again"
    assert 'aria-hidden="true"' in nav.group(0), "the closed drawer is exposed to assistive tech"
    assert "drawer.inert = !open" in PAGE, "the JS does not keep `inert` in step with the class"
    toggle = re.search(r"<button class=\"nav-toggle\"[^>]*>", PAGE)
    assert toggle and 'aria-controls="drawer"' in toggle.group(0), "the toggle does not name what it opens"
    assert toggle and "aria-expanded" in toggle.group(0), "the toggle does not report its state"


def test_a_reader_who_asked_for_no_motion_gets_none():
    """Zero of these rules existed while the page shipped 24 animations and transitions."""
    block = re.search(r"@media \(prefers-reduced-motion: reduce\)\s*\{(.*?)\n  \}", PAGE, re.DOTALL)
    assert block, "no prefers-reduced-motion block"
    body = block.group(1)
    assert "animation-duration" in body and "transition-duration" in body, (
        "the block must neutralise both animations and transitions, not one of them")
    assert "!important" in body, "without !important the inline and later rules win"


def test_the_search_field_has_a_label_and_the_results_have_a_summary_region():
    """A placeholder is not a label (`aria-label`-free inputs announce as "edit text"), and results
    that appear silently leave a screen-reader user without the count they can see."""
    assert re.search(r"<label[^>]*for=\"search-input\"[^>]*>", PAGE), "the search input has no label"
    region = re.search(r"<div id=\"search-status\"[^>]*>", PAGE)
    assert region, "no result-summary region"
    assert 'role="status"' in region.group(0) and 'aria-live="polite"' in region.group(0), region.group(0)
    assert "search-status" in PAGE.split("function searchLessons")[1], (
        "the summary region exists but the search never writes to it")
    assert "sr-only" in PAGE, "the label and summary need the visually-hidden utility"
