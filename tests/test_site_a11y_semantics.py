#!/usr/bin/env python3
"""The site's heading outline and its disclosure controls must mean something.

Why this file exists
--------------------
The homepage had one `<h1>` (the site title) and **no `<h2>` at all** — its next headings were
`<h3>`, so a screen reader's heading list went h1 → h3 and the sections in between were invisible
to it. The two section titles ("网络活动", "贡献排行") were plain `<div>`s, and the caveat printed
next to them ("自建聚合调用计数 · 非 Cloudflare 边缘指标 …") sat *inside* the title element, so it
would have become part of the heading's accessible name.

The search page had the same defect in a different shape: the result title was a `<div>`, and the
lesson body inside a result card rendered `##` as an `<h2>` — so the document read h1 → h3 → h2,
a skip and an inversion at once. The "Read lesson" button also did not say whether it had expanded
anything, so the state existed only as a change in the button's *text*.

Each assertion below can go red: drop a heading level, put the caveat back inside the title, or
remove one `aria-expanded` write, and the matching test fails.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
HOMEPAGE = (REPO / "docs" / "index.html").read_text(encoding="utf-8")
SEARCH = (REPO / "docs" / "search" / "index.html").read_text(encoding="utf-8")


def _levels(markup: str) -> list[int]:
    """Heading levels in document order."""
    return [int(m) for m in re.findall(r"<h([1-6])\b", markup)]


def _assert_no_skip(levels: list[int], where: str) -> None:
    """A heading may go down any number of levels, but up at most one."""
    for previous, current in zip(levels, levels[1:]):
        assert current <= previous + 1, (
            f"{where}: a heading jumps from h{previous} to h{current}; the outline skips a level"
        )


class TestHomepageOutline:
    def test_the_outline_starts_at_the_only_h1(self):
        levels = _levels(HOMEPAGE)
        assert levels, "the homepage has no headings at all"
        assert levels[0] == 1, f"the first heading is h{levels[0]}, not the h1"

    def test_no_heading_level_is_skipped(self):
        _assert_no_skip(_levels(HOMEPAGE), "docs/index.html")

    def test_the_sections_are_headings_not_divs(self):
        """The section titles were divs, so they were not in the outline at all."""
        assert HOMEPAGE.count('<div class="section-title"') == 0, (
            "a section title is still a div — it is missing from the heading outline"
        )
        assert HOMEPAGE.count('<h2 class="section-title"') == 2, (
            "expected the two section titles (网络活动, 贡献排行) to be h2"
        )

    def test_the_caveat_is_not_part_of_the_heading_name(self):
        """A caveat printed beside a title must not become the title's accessible name.

        The caveat stays in the heading element — moving it out re-flowed the flex row and moved
        the text 13px — so the name is pinned with `aria-labelledby` instead.
        """
        heading = re.search(r'<h2 class="section-title"[^>]*>.*?</h2>', HOMEPAGE, re.S)
        assert heading, "the network-activity section title is not an h2"
        assert 'class="panel-note"' in heading.group(0), (
            "the caveat is no longer printed beside the section title"
        )
        labelled_by = re.search(r'aria-labelledby="([A-Za-z0-9_-]+)"', heading.group(0))
        assert labelled_by, (
            "the heading has no aria-labelledby, so a screen reader reads the caveat as part of "
            "the section name"
        )
        target = re.search(r'id="%s"[^>]*>([^<]*)' % re.escape(labelled_by.group(1)), HOMEPAGE)
        assert target, "aria-labelledby points at an element that does not exist"
        assert "panel-note" not in target.group(1), "the labelled text is the caveat itself"

    def test_the_modal_headings_keep_their_own_look(self):
        """The modal headings moved from h3 to h2; the rule that styles them has to follow."""
        assert ".modal-section h2 {" in HOMEPAGE, (
            "the modal headings are h2 now, but the CSS still targets h3 — they lose their size"
        )
        assert ".modal-section h3 {" not in HOMEPAGE

    def test_the_homepage_still_has_exactly_one_h1(self):
        assert len(re.findall(r"<h1\b", HOMEPAGE)) == 1


class TestSearchOutline:
    def test_the_page_still_has_exactly_one_h1(self):
        assert len(re.findall(r"<h1\b", SEARCH)) == 1

    def test_the_result_title_is_a_heading(self):
        assert "'<h2 class=\"result-title\">'" in SEARCH, (
            "the result title is not a heading — a result is a section of the results list"
        )

    def test_the_lesson_body_starts_one_level_below_the_result_title(self):
        """`##` in a lesson body is inside a card whose title is an h2, so it must be an h3."""
        assert "renderMarkdown(clipped || t('noPreview'), 3)" in SEARCH, (
            "the preview renders the lesson's own headings at the page's top level, so the outline "
            "reads h1 → h2 (result) → h2 (body)"
        )
        assert "function renderMarkdown(text, headingLevel = 2)" in SEARCH


class TestThePreviewButtonWorks:
    """The control that opens the preview has to actually open it.

    The fix for "a Helpful click also opened the preview and spent one of the 20 anonymous reads
    per minute" (#3539 C5) added `button` to the click handler's exclusion list. That also
    swallowed the preview's own button — the one control whose whole purpose is to open the
    preview. On the live site "Read lesson" did nothing at all, and the body could only be reached
    by clicking the card around it (verified on misakanet.org/search/ on 2026-10-20).
    """

    def test_the_exclusion_list_does_not_swallow_the_preview_button(self):
        # The card handler's exclusion list is the one that also mentions `summary`; the feedback
        # handler has its own `closest('.feedback-btn')` earlier in the file.
        lists = re.findall(r"closest\('([^']*feedback-btn[^']*)'\)", SEARCH)
        card_lists = [one for one in lists if "summary" in one]
        assert card_lists, "the card click handler no longer excludes the feedback buttons"
        selectors = [s.strip() for s in card_lists[0].split(",")]
        assert "button" not in selectors, (
            "the exclusion list contains a bare `button`, which swallows the preview's own button "
            "— the control that opens the preview"
        )
        assert ".feedback-btn" in selectors, "the feedback buttons must stay excluded"

    def test_the_feedback_buttons_are_still_excluded(self):
        """The reason the exclusion exists: a Helpful click must not open the preview."""
        assert ".feedback-btn, summary, details" in SEARCH

    def test_the_keyboard_path_reaches_the_button(self):
        """A focused button fires a click, so the same handler serves the keyboard."""
        assert "event.target.closest('a,button')" in SEARCH, (
            "the keydown handler must let the button's own click through"
        )


class TestTheDisclosureControl:
    """The button that opens the preview has to say whether it is open."""

    def test_the_button_declares_its_initial_state_and_its_target(self):
        assert 'data-action="preview" aria-expanded="false"' in SEARCH
        assert "aria-controls=\"preview-' + r._index + '\"" in SEARCH
        assert "'<div class=\"lesson-preview\" id=\"preview-' + r._index + '\" hidden></div>'" in SEARCH

    def test_opening_the_preview_updates_the_state(self):
        assert "btn.setAttribute('aria-expanded', 'true');" in SEARCH, (
            "opening a preview does not tell the assistive technology that it is open"
        )

    def test_closing_the_preview_updates_the_state(self):
        assert "btn.setAttribute('aria-expanded', panel.hidden ? 'false' : 'true');" in SEARCH, (
            "closing a preview does not tell the assistive technology that it is closed"
        )

    def test_collapsing_another_card_puts_that_card_back(self):
        """Only one preview is open at a time, so the card that closes must say it closed."""
        assert "otherBtn.setAttribute('aria-expanded', 'false');" in SEARCH
