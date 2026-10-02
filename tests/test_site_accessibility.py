#!/usr/bin/env python3
"""The front page has to work without a mouse and without motion.

Measured on `docs/index.html` on 2026-10-02, before this change: **0** `<h1>`, **0** `<main>`, **0**
`prefers-reduced-motion` rules — against 11 `@keyframes` and 13 `animation:` declarations
(plus 32 `transition:`) — and **0**
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


def test_the_search_field_has_a_label_and_the_results_have_a_summary_region():
    """A placeholder is not a label (`aria-label`-free inputs announce as "edit text"), and results
    that appear silently leave a screen-reader user without the count they can see."""
    assert re.search(r"<label[^>]*for=\"search-input\"[^>]*>", PAGE), "the search input has no label"
    region = re.search(r"<div id=\"search-status\"[^>]*>", PAGE)
    assert region, "no result-summary region"
    assert 'role="status"' in region.group(0) and 'aria-live="polite"' in region.group(0), region.group(0)
    assert "sr-only" in PAGE, "the label and summary need the visually-hidden utility"


def _function_body(name: str) -> str:
    """One function's source, from its declaration to the next top-level `function`."""
    tail = PAGE.split(f"function {name}", 1)[1]
    return tail.split("\nfunction ", 1)[0]


def _scan(text: str):
    """Yield ``(index, char, depth)`` for every character, with quotes understood.

    `depth` is the block nesting **at** that character: a `{` is reported at the depth outside it, a `}`
    at the depth inside it. Braces are yielded rather than swallowed, because the two helpers below need
    them — the first version of this scanner dropped them and brace matching could never close.
    Backticks count as strings, which also keeps `${…}` template braces out of the depth.
    """
    depth, quote, index = 0, None, 0
    while index < len(text):
        char = text[index]
        if quote:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
            index += 1
            continue
        if char in "\"'`":
            quote = char
            yield index, char, depth
            index += 1
            continue
        if char == "{":
            yield index, char, depth
            depth += 1
            index += 1
            continue
        if char == "}":
            depth -= 1
            yield index, char, depth
            index += 1
            continue
        yield index, char, depth
        index += 1


def _strip_js_comments(text: str) -> str:
    """Drop `//…` and `/*…*/` comments that sit **outside** string literals.

    Quote-aware on purpose. The first version dropped only *whole-line* comments — written that way to
    avoid cutting a URL's `//` in half — and a review walked through it with a **trailing** comment
    (`display = "block";  // used to be: if (status) status.textContent = …` plus deleting the real
    write): 9 passed, and the page kept announcing the previous query. Understanding strings removes the
    tradeoff — a `//` inside quotes survives because it is in quotes, not because of where the line ends.
    """
    keep, index, quote = [], 0, None
    while index < len(text):
        char = text[index]
        if quote:
            keep.append(char)
            if char == "\\":
                keep.append(text[index + 1:index + 2])
                index += 2
                continue
            if char == quote:
                quote = None
            index += 1
            continue
        if char in "\"'`":
            quote = char
            keep.append(char)
            index += 1
            continue
        if char == "/" and text[index + 1:index + 2] == "/":
            index = text.find("\n", index)
            if index == -1:
                break
            continue
        if char == "/" and text[index + 1:index + 2] == "*":
            end = text.find("*/", index + 2)
            index = len(text) if end == -1 else end + 2
            continue
        keep.append(char)
        index += 1
    return "".join(keep)


def _brace_block(text: str, start: int) -> str:
    """The `{…}` block beginning at or after `start`, found with the same quote-aware scanner.

    Braces, not a character window: an ordinary copy edit (reordering the miss panel's three `innerHTML`
    lines) was enough to slide another branch's write into a window and keep the rule green while the
    browser showed a stale summary.
    """
    opening = text.index("{", start)
    depth = 0
    for index, char, _ in _scan(text[opening:]):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[opening:opening + index + 1]
    raise AssertionError("unbalanced braces in searchLessons — this helper needs updating")


def _has_write_at_depth(text: str, depth: int) -> bool:
    """True when `status.textContent =` is a **direct** statement at that depth.

    Depth, because "somewhere in the block" is satisfied by a write nested in another condition —
    `if (rawQ.length > 200) { if (status) status.textContent = … }` passed while a normal query wrote
    nothing (a review built exactly that, and it is not dead code: the branch is reachable).
    """
    pattern = re.compile(r"status\.textContent\s*=")
    for index, _char, current in _scan(text):
        if current == depth and pattern.match(text, index):
            return True
    return False


def test_the_summary_is_written_inside_each_branch_block():
    """Per branch **block**, located by braces, with the write a direct statement of that block.

    Three earlier versions of this rule were beaten, each worth remembering: a count of assignments
    (defeated by deleting one write and adding two dummies elsewhere); a ±window around each branch's
    copy (defeated by reordering that copy, which slid another branch's write into the window); and
    whole-line-only comment stripping (defeated by a *trailing* comment containing the very text the rule
    looks for). Braces do not move when copy does, strings are understood before comments are stripped,
    and depth keeps a nested conditional from standing in for the statement itself.

    Known limit, stated rather than implied: this reads the source, so `if (false) { status.textContent
    = … }` inside a block satisfies it — measured. That is true of every rule in this file and is not
    fixable without executing the page.
    """
    body = _strip_js_comments(_function_body("searchLessons"))
    miss_start = body.index("if (scored.length === 0)")
    miss_block = _brace_block(body, miss_start)
    # The two `if` bodies get the strict form: a write that is a **direct** statement of that block, so
    # a write nested in another condition cannot stand in for it. The success path is the remainder of
    # the function — not a balanced slice, so its baseline depth is not comparable — and existence is
    # what is checkable there.
    blocks = {
        "cleared query": _brace_block(body, body.index("if (!q || !_allLessons)")),
        "no match": miss_block,
    }
    for branch, block in blocks.items():
        assert _has_write_at_depth(block, 1), (
            f"the {branch} branch can reach its outcome without a direct write to the summary region")
    assert re.search(r"status\.textContent\s*=", body[miss_start + len(miss_block):]), (
        "the results branch can reach its outcome without writing the summary region")


def test_a_blocked_data_load_is_announced_not_just_painted():
    """`renderErrorBoundaryUI` is reachable — aborting *both* lesson payloads shows its panel (aborting
    only `lessons-lite.json` does not: the page falls back to the full corpus) — and the panel is
    visible while a screen reader gets nothing unless the live region is written too.

    Like every rule in this file it reads the source, so a *comment* containing `status.textContent =`
    would satisfy it; a review measured that general property of regex assertions. It is kept because
    the concrete regression it prevents is one edit away, and the alternative is not to check at all.
    """
    body = _function_body("renderErrorBoundaryUI")
    assert re.search(r"status\.textContent\s*=", body), (
        "the error panel is painted but never announced through the live region")


def test_hiding_the_results_clears_the_summary():
    """The blur handler hides the panel after 200 ms; a summary that keeps saying "Results are listed
    below the search box" then describes something that is no longer on screen."""
    handler = re.search(r"setTimeout\(\(\)=>\{document\.getElementById\('search-results'\)\.style\.display='none';(.*?)\}?,200\)", PAGE)
    assert handler and "search-status" in handler.group(1), (
        "hiding the results leaves the summary claiming they are listed below")


def test_a_reader_who_asked_for_no_motion_gets_none():
    """Zero of these rules existed while the page shipped 11 @keyframes and 13 animation declarations."""
    block = re.search(r"@media \(prefers-reduced-motion: reduce\)\s*\{(.*?)\n  \}", PAGE, re.DOTALL)
    assert block, "no prefers-reduced-motion block"
    body = block.group(1)
    assert "animation-duration" in body and "transition-duration" in body, (
        "the block must neutralise both animations and transitions, not one of them")
    assert "!important" in body, "without !important the inline and later rules win"
    # The selector matters as much as the declarations: narrowing it to `.drawer` would leave every
    # other animation on the page running, and a rule that only counts declarations stays green.
    assert "*, *::before, *::after" in body, (
        "the block no longer covers every element, so most of the page still moves")


def test_the_nav_partial_carries_the_closed_state_too():
    """The drawer is *generated* from `docs/_partials/nav.html`, and `sync_site_partials.py --check`
    enforces that the page matches it.

    Editing only `docs/index.html` therefore passes every rule above and still fails the repository:
    the first version of this change was caught exactly here, because the next sync would have put the
    focusable drawer back. The source of truth has to carry the attribute, not just the page.
    """
    partial = (REPO / "docs" / "_partials" / "nav.html").read_text(encoding="utf-8")
    nav = re.search(r'<nav class="drawer"[^>]*>', partial)
    assert nav, "the partial no longer defines the drawer; this test needs updating"
    assert "inert" in nav.group(0), "the partial would regenerate a focusable closed drawer"
    assert 'aria-hidden="true"' in nav.group(0), "the partial exposes the closed drawer to assistive tech"
