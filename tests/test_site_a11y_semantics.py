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

The result *card* had the same gap one level out: it is a `div[tabindex="0"]` that Enter and Space
activate to toggle the preview panel, and it said neither that it was a control nor whether its
panel was open (#3539 R2).

Each assertion below can go red: drop a heading level, put the caveat back inside the title, remove
one `aria-expanded` write, or take the role off the card, and the matching test fails.
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


def _window(text: str, start: str, end: str) -> str:
    """The slice between two anchors — one branch of a function, roughly.

    A branch is found by its own anchors rather than by a line range or a character window, so a
    copy edit above it cannot slide a different branch into the slice.
    """
    begin = text.index(start)
    finish = text.index(end, begin + len(start))
    return text[begin:finish]


def _function_body(name: str) -> str:
    """One function's source, from its declaration to the next top-level `function`."""
    tail = SEARCH.split(f"function {name}", 1)[1]
    return tail.split("\nfunction ", 1)[0]


def _canonical(fragment: str) -> str:
    """A markup fragment reduced to what it says: the interpolated variables kept as `${…}`.

    The page builds the card's tag from several string literals, so the interpolated JavaScript
    becomes a `${…}` marker and the literals are joined. The marker keeps the interpolated
    *variable*, so a card that pointed at a different id than the one its title carries still
    fails — and the whitespace around a marker is dropped, so the two spellings of one id compare
    equal.
    """
    fragment = re.sub(r"\+\s*([A-Za-z_$][\w.$]*)\s*\+", r"${\1}", fragment)
    fragment = fragment.replace("'", "").replace("+", "")
    fragment = re.sub(r"\s*\$\{", "${", fragment)
    return re.sub(r"\}\s*", "}", fragment)


def _card_attributes() -> str:
    """The result card's attributes, as the page builds them."""
    match = re.search(r"'<div class=\"result\"[\s\S]*?data-id=\"' \+ id \+ '\">'", SEARCH)
    assert match, "the result card markup moved; this test reads its opening tag"
    return _canonical(match.group(0))


def _result_title_id() -> str:
    """The id the result title carries, as the page builds it."""
    match = re.search(r"'<h2 class=\"result-title\" id=\"(.*?)\"", SEARCH)
    assert match, "the result title carries no id for the card to point at"
    return _canonical(match.group(1))


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
        assert "'<h2 class=\"result-title\"" in SEARCH, (
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


class TestTheResultCardIsAControl:
    """The card is focusable, Enter/Space open it, and it toggles the panel below it.

    It said none of that. With no `role` a screen reader read a focusable block of text that
    behaved like a button, and with no expansion state nothing announced whether the panel was
    open — the state existed only as a change in the *inner* button's text (#3539 R2).

    The role is `button` because that is what the card is: it is in the tab order, Enter and
    Space activate it, and it toggles a disclosure. `role="group"` was measured instead and
    rejected: Chromium drops `aria-expanded` on a group, so the state the issue asks for would
    not be announced at all. The name is pinned to the title with `aria-labelledby`, because a
    `role="button"` takes its name from its contents — and the card's contents are the title, the
    summary, the tags and every button label in it.
    """

    def test_the_card_declares_the_role_its_interaction_implies(self):
        attributes = _card_attributes()
        assert 'role="button"' in attributes, (
            "the card is focusable and activated by Enter/Space, so it has to carry a role — "
            "without one it reads as a focusable block of text"
        )
        assert "aria-controls=" in attributes, (
            "the card has to name the panel it controls"
        )

    def test_the_card_starts_collapsed_like_the_panel_it_controls(self):
        attributes = _card_attributes()
        assert 'aria-expanded="false"' in attributes, (
            "the card's panel starts hidden, so the card has to start collapsed"
        )

    def test_the_card_is_named_by_its_title(self):
        """A `role="button"` names itself from its contents unless it is told otherwise.

        Computed from the contents the name is the whole card — title, summary, tags and every
        button label in it. The title names the card, and the title is the heading, so the
        reference has to resolve to that heading and to that heading only.
        """
        attributes = _card_attributes()
        assert "aria-labelledby=" in attributes, (
            "the card's name would be computed from its contents, which is the whole card"
        )
        label = re.search(r'aria-labelledby="([^"]*)"', attributes).group(1)
        assert label == _result_title_id(), (
            "the card points at a title id that no title carries"
        )

    def test_opening_the_panel_expands_the_card(self):
        """The path that opens a panel for the first time (the body is still being fetched)."""
        opening = _window(_function_body("togglePreview"), "panel.hidden = false;", "try {")
        assert "card.setAttribute('aria-expanded', 'true');" in opening, (
            "the card opens its panel without saying that it is open"
        )

    def test_closing_and_reopening_the_panel_flips_the_card(self):
        """The path that toggles a panel that was already loaded.

        The state is read off the panel rather than written out by hand: a hard-coded `'true'`
        here would leave the card claiming to be open after the panel was closed.
        """
        toggling = _window(
            _function_body("togglePreview"),
            "if (panel.dataset.loaded === 'true')",
            "panel.hidden = false;",
        )
        assert "card.setAttribute('aria-expanded', panel.hidden ? 'false' : 'true');" in toggling, (
            "the card's state has to follow the panel it controls"
        )

    def test_collapsing_another_card_puts_that_card_back(self):
        """Opening a card closes the others, so the cards that close have to say they closed."""
        auto_collapse = _window(
            _function_body("togglePreview"),
            "openPanels.forEach",
            "if (panel.dataset.loaded === 'true')",
        )
        assert "otherCard.setAttribute('aria-expanded', 'false');" in auto_collapse, (
            "the card that was auto-collapsed still claims to be expanded"
        )

    def test_the_card_is_still_reachable_and_activatable_by_keyboard(self):
        """The role must not cost the card its keyboard path."""
        attributes = _card_attributes()
        assert 'tabindex="0"' in attributes, "the card fell out of the tab order"
        handler = _window(
            SEARCH,
            "document.getElementById('results').addEventListener('keydown'",
            "\n});",
        )
        assert "event.key !== 'Enter' && event.key !== ' '" in handler, (
            "the card is activated by Enter and Space, so the handler has to keep listening for both"
        )
        assert "togglePreview(Number(card.dataset.index));" in handler, (
            "the keyboard path no longer opens the card"
        )
