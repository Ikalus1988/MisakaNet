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

import json
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


def _body(source: str, name: str) -> str:
    """The body of `function <name>(…) { … }` — braces counted, so nested blocks are fine.

    Scoping an assertion to one function is what makes it able to fail. The mutation audit
    caught the difference: the line `if (first) first.focus();` exists **twice** in the page —
    once in the onboarding dialog and once in the nav drawer — so an assertion that only said
    "the page contains this line" was satisfied by the drawer's copy, and deleting the dialog's
    own focus call left the gate green.
    """
    start = source.index(f"function {name}(")
    brace = source.index("{", start)
    depth = 0
    for i in range(brace, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return source[brace:i + 1]
    raise AssertionError(f"function {name}() has no closing brace")


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


def _fold_toggle_markup() -> str:
    """The fold button's markup, as the page builds it."""
    match = re.search(r"'<button class=\"fold-toggle\"[\s\S]*?'</button>'", SEARCH)
    assert match, "the fold button markup moved; this test reads it"
    return match.group(0)


def _fold_toggle_tag() -> str:
    """The fold button's opening tag, as the page builds it."""
    match = re.search(r"'<button class=\"fold-toggle\"[\s\S]*?>'", _fold_toggle_markup())
    assert match, "the fold button markup moved; this test reads its opening tag"
    return _canonical(match.group(0))


def _modal_content_tag() -> str:
    """The onboarding modal's content element — the dialog."""
    match = re.search(r"<div class=\"modal-content\"[^>]*>", HOMEPAGE)
    assert match, "the onboarding modal's markup moved; this test reads its opening tag"
    return match.group(0)


def _modal_close_tag() -> str:
    """The onboarding modal's close control."""
    match = re.search(r"<button class=\"modal-close\"[^>]*>", HOMEPAGE)
    assert match, "the modal's close button moved; this test reads its opening tag"
    return match.group(0)


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


class TestTheFoldedListIsADisclosure:
    """The "common references" list is folded behind a button that said nothing about it.

    The state lived in two places at once — the `.open` class, which only rotates the arrow, and
    the panel's `hidden` — and neither of them is something a screen reader can hear. The reader
    was told the list was there and not whether it was open, and the arrow was read out as part
    of the button's name on top of that.
    """

    def test_the_button_declares_its_initial_state_and_its_target(self):
        tag = _fold_toggle_tag()
        assert 'aria-expanded="false"' in tag, (
            "the list starts folded, so the button has to start collapsed"
        )
        assert 'aria-controls="fold-common"' in tag, (
            "the button has to name the list it opens"
        )

    def test_the_list_the_button_names_exists_and_starts_hidden(self):
        assert "'<div id=\"fold-common\" hidden>'" in SEARCH, (
            "the panel the button names has to exist, and it starts hidden"
        )

    def test_the_button_uses_the_function_that_keeps_the_state(self):
        assert 'onclick="toggleFold(this)"' in _fold_toggle_markup(), (
            "the button has to call the function that writes the state, not toggle the class and "
            "the `hidden` attribute on its own"
        )

    def test_the_state_is_read_off_the_panel(self):
        """Not toggled twice in a row: the panel is what the reader sees, the arrow a picture of it.

        Toggling the class and the `hidden` attribute independently is what let the two drift
        apart — and it is the reason the state has to be read off the panel rather than flipped.
        """
        body = _function_body("toggleFold")
        assert "panel.hidden = !panel.hidden;" in body, (
            "the panel is the state — it has to be what the button flips"
        )
        assert "button.setAttribute('aria-expanded', panel.hidden ? 'false' : 'true');" in body, (
            "the button's state has to be read off the panel, so the two cannot drift apart"
        )
        assert "button.classList.toggle('open', !panel.hidden);" in body, (
            "the arrow's rotation has to follow the panel too"
        )

    def test_the_button_is_named_by_its_label_and_not_by_the_arrow(self):
        assert '<span class="arrow" aria-hidden="true">' in SEARCH, (
            "the arrow is decoration — without aria-hidden it is read out as part of the name"
        )
        assert "t('sectionCommon'" in _fold_toggle_markup(), (
            "the button has to be named by its label, which is the localised one"
        )


class TestTheOnboardingModalIsADialog:
    """The onboarding modal was a `<div>` that a screen reader read as a pile of text.

    It had no `role="dialog"`, no `aria-modal`, and nothing named it — so a reader heard the
    modal's four sections and the page behind it as one long run of text. The close control was a
    `✕` with no accessible name at all, and the control that opens the modal was a `?`, whose
    `title` the name computation never reached: a button's name comes from its content first, so
    it read as the glyph.
    """

    def test_the_modal_is_a_dialog(self):
        tag = _modal_content_tag()
        assert 'role="dialog"' in tag, (
            "the modal is a dialog — without the role a screen reader reads it as plain text"
        )
        assert 'aria-modal="true"' in tag, (
            "the modal covers the page, so it has to say so — without aria-modal the content "
            "behind it stays in the reading order"
        )

    def test_the_dialog_is_named_by_the_title_that_exists(self):
        tag = _modal_content_tag()
        labelled_by = re.search(r'aria-labelledby="([^"]+)"', tag)
        assert labelled_by, (
            "the dialog has no name — a screen reader announces an unnamed dialog as just "
            '"dialog"'
        )
        target = labelled_by.group(1)
        assert re.search(r'id="%s"' % re.escape(target), HOMEPAGE), (
            "aria-labelledby points at an element that does not exist"
        )
        assert re.search(
            r'<div class="modal-title"[^>]*id="%s"' % re.escape(target), HOMEPAGE
        ), "the dialog has to be named by the title that is on screen"

    def test_the_close_control_has_a_name_and_keeps_its_glyph(self):
        tag = _modal_close_tag()
        label = re.search(r'aria-label="([^"]*)"', tag)
        assert label, (
            "the close control is a `✕` — without a name a screen reader reads the glyph"
        )
        assert label.group(1).strip(), "the close control's accessible name is empty"
        assert ">✕</button>" in HOMEPAGE, (
            "the close control lost its glyph — the name was to be added, not the mark replaced"
        )

    def test_the_control_that_opens_the_modal_has_a_name(self):
        """The opener's `title` was never its name.

        A button's accessible name comes from its content before its `title`, and the content is
        `?` — so the title was decoration and the button read as the glyph.
        """
        opener = re.search(r"<button class=\"help-btn\"[^>]*>", HOMEPAGE)
        assert opener, "the modal's opener moved; this test reads its opening tag"
        label = re.search(r'aria-label="([^"]*)"', opener.group(0))
        assert label and label.group(1).strip(), (
            "the opener is a `?` — without a name a screen reader reads the glyph"
        )


class TestTheOnboardingDialogBehavesLikeOne:
    """`role="dialog"` is the semantics; the behaviour is what a keyboard user actually meets.

    The dialog said `aria-modal="true"` and behaved like a picture of one: the page behind it was
    still tabbable, opening it left the focus on the `?` button *behind* the dialog, and closing it
    dropped the focus wherever the browser happened to be. The nav drawer in the same file already
    had the right pattern — focus in, focus back to the control that opened it, Escape does the
    same — so this is that mechanism applied to the one panel that did not have it.

    The close button's name was also a fixed English string on a page that translates everything
    else, so a Chinese-speaking screen-reader user heard "Close".
    """

    def test_the_trigger_says_whether_the_dialog_is_open(self):
        assert 'aria-expanded="false" aria-controls="onboarding-modal"' in HOMEPAGE, (
            "the button that opens the dialog must say whether it is open and what it controls"
        )

    def test_opening_the_dialog_updates_the_state(self):
        assert ("trigger.setAttribute('aria-expanded', open ? 'true' : 'false');"
                in _body(HOMEPAGE, "setModal")), (
            "the opener does not learn that the dialog is open"
        )

    def test_opening_the_dialog_moves_the_focus_into_it(self):
        body = _body(HOMEPAGE, "setModal")
        assert "_modalReturnFocus = document.activeElement;" in body, (
            "the dialog does not remember where the focus came from, so it cannot give it back"
        )
        assert "function modalFocusables()" in HOMEPAGE, (
            "the dialog does not look for something to focus"
        )
        assert "modalFocusables()[0]" in body, (
            "opening the dialog leaves the focus on the button behind it"
        )
        assert "first.focus();" in body, (
            "opening the dialog leaves the focus on the button behind it"
        )

    def test_closing_the_dialog_hands_the_focus_back(self):
        assert "_modalReturnFocus.focus();" in _body(HOMEPAGE, "setModal"), (
            "closing the dialog drops the focus instead of returning it to the opener"
        )

    def test_the_page_behind_the_dialog_is_inert_while_it_is_open(self):
        body = _body(HOMEPAGE, "setModalBackgroundInert")
        assert "sibling.inert = true;" in body, (
            "the elements behind the dialog are never made inert"
        )
        assert "el.inert = false;" in body, (
            "closing the dialog leaves the page behind it inert forever"
        )
        modal = _body(HOMEPAGE, "setModal")
        assert "setModalBackgroundInert(true);" in modal and "setModalBackgroundInert(false);" in modal, (
            "the background is never handed back"
        )

    def test_the_inert_walk_starts_at_the_dialog_and_climbs(self):
        """The dialog is not a child of `<body>`; it lives inside `<main>` inside `.container`.

        The first version of this made `body`'s children inert, which made the *container* inert,
        and the container is an ancestor of the dialog — so the dialog was inert too and could not
        take the focus. "Everything except the dialog" is the set of siblings on the way up, not
        the set of `<body>`'s children.
        """
        body = _body(HOMEPAGE, "setModalBackgroundInert")
        assert "body > *:not(#onboarding-modal)" not in body, (
            "the dialog is not a child of `<body>`; inerting `<body>`'s children inerts the dialog "
            "with them"
        )
        assert "const parent = node.parentElement;" in body and "node = parent;" in body, (
            "the inert walk does not climb out of the dialog's ancestors"
        )
        assert "if (sibling !== node && !sibling.inert)" in body, (
            "the walk must skip the dialog itself, and must not touch an element that is already "
            "inert"
        )

    def test_closing_the_dialog_does_not_uninert_the_drawer(self):
        """The drawer is inert on purpose when it is closed.

        If the modal's bookkeeping records elements that were already inert, closing the modal
        hands the drawer back to the keyboard — and the drawer has 17 links in it that are not on
        screen. Only the elements the modal itself made inert get handed back.
        """
        body = _body(HOMEPAGE, "setModalBackgroundInert")
        assert "_modalInerted.push(sibling);" in body, (
            "the elements the dialog made inert are not recorded, so they cannot be handed back"
        )
        assert "for (const el of _modalInerted) el.inert = false;" in body, (
            "closing the dialog re-enables elements it never touched"
        )

    def test_escape_closes_the_dialog_and_returns_the_focus(self):
        assert ("if (document.getElementById('onboarding-modal').classList.contains('open')) "
                "setModal(false, true);" in _body(HOMEPAGE, "handleGlobalKeys")), (
            "Escape closes the dialog without handing the focus back"
        )

    def test_the_global_key_handler_is_registered(self):
        """The Escape branch and the Cmd+K branch live in the same listener.

        A handler that is defined but never registered is a comment, and both of those
        behaviours would be gone while every other assertion stayed green.
        """
        assert "document.addEventListener('keydown', handleGlobalKeys);" in HOMEPAGE, (
            "the global key handler is defined but never registered"
        )

    def test_the_focus_does_not_leave_the_dialog_while_it_is_open(self):
        """`inert` takes the background out of the tab order, but the focus still walked off.

        Measured in Chromium: tabbing past the last link in the dialog left it — `document
        .activeElement` became `<body>` (the browser's own chrome) and only came back on the
        next Tab. `aria-modal="true"` and the ARIA Authoring Practices both say the focus stays
        inside the dialog while it is open, so the last element hands it to the first.
        """
        assert "document.addEventListener('keydown', handleModalTab);" in HOMEPAGE, (
            "the Tab handler is defined but never registered — the focus still walks out"
        )
        body = _body(HOMEPAGE, "handleModalTab")
        assert "if (e.key !== 'Tab') return;" in body, (
            "nothing keeps Tab inside the dialog"
        )
        assert "if (!overlay.classList.contains('open')) return;" in body, (
            "the dialog steals the Tab key even when it is closed"
        )
        assert "const last = items[items.length - 1];" in body, (
            "the dialog does not know where its tab ring ends"
        )
        assert "e.preventDefault();" in body and "last.focus();" in body, (
            "Tab past the last element is not wrapped back to the first"
        )
        assert "first.focus();" in body, (
            "Tab past the last element is not wrapped back to the first"
        )

    def test_the_search_shortcut_does_not_fire_from_behind_the_dialog(self):
        """The background is inert, so the search box cannot take the focus.

        `input.focus()` on an inert element does nothing at all, so the shortcut used to flash
        the search field's border as if it had worked while the focus never left the dialog.
        """
        assert ("if (document.getElementById('onboarding-modal').classList.contains('open')) "
                "return;" in _body(HOMEPAGE, "handleGlobalKeys")), (
            "Cmd+K still flashes the search box behind an open dialog, where it cannot be focused"
        )

    def test_the_close_button_is_named_in_the_readers_language(self):
        assert 'aria-label="Close" data-i18n-aria="modalClose"' in HOMEPAGE
        for locale in ("en", "zh"):
            table = json.loads(
                (REPO / "docs" / "locales" / f"{locale}.json").read_text(encoding="utf-8")
            )
            assert "modalClose" in table, f"{locale}.json has no modalClose label"
            assert table["modalClose"].strip(), f"{locale}.json's modalClose is empty"

    def test_the_opener_is_named_in_the_readers_language_too(self):
        assert 'data-i18n-aria="modalWhatTitle"' in HOMEPAGE
        assert 'data-i18n-title="modalWhatTitle"' in HOMEPAGE

    def test_the_translator_can_reach_an_accessible_name(self):
        """`data-i18n` replaces `textContent`, so it can never reach an attribute."""
        assert "document.querySelectorAll('[data-i18n-aria]')" in HOMEPAGE
        assert "el.setAttribute('aria-label', value);" in HOMEPAGE
        assert "document.querySelectorAll('[data-i18n-title]')" in HOMEPAGE
        assert "el.setAttribute('title', value);" in HOMEPAGE
