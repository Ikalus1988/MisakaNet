#!/usr/bin/env python3
"""Which ranking the search box uses, and when — the split that step 3's measurement decided.

Measured 2026-09-30 by `scripts/bench_search_parity.mjs` (it executes the page's own scorer): the local
scorer is a **substring** match over four metadata fields, so it never returns fewer than five rows and its
extra hits are mostly false positives; it cannot see lesson bodies. The server ranks by BM25/IDF over the
bodies too, but this worker shares **one** anti-burst window (20 reads / 60 s) across every read entry
point — so a server call per keystroke would throttle a real visitor.

Hence: typing stays local, and the **committed** query (Enter, or a `?q=` deep link) asks the Worker. This
file pins that split, because "which one runs when" is the whole design and it is invisible in a diff.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SEARCH = REPO / "docs" / "search" / "index.html"
HOME = REPO / "docs" / "index.html"


def search_page() -> str:
    return SEARCH.read_text(encoding="utf-8")


def handler_body(source: str, selector: str, event: str) -> str:
    """The body of `document.getElementById(selector).addEventListener(event, …)`."""
    pattern = re.compile(
        r"getElementById\(\s*['\"]" + re.escape(selector) + r"['\"]\s*\)\s*\.addEventListener\(\s*['\"]"
        + re.escape(event) + r"['\"]\s*,(.*?)\n\}\);", re.S)
    match = pattern.search(source)
    assert match, f"the {selector} {event} handler moved — this rule must move with it"
    return match.group(1)


def test_typing_stays_local_so_a_keystroke_cannot_throttle_a_visitor():
    body = handler_body(search_page(), "q", "input")
    assert "runSearch(" in body, "the input handler must render the local results"
    assert "runServerSearch(" not in body, (
        "a server call per keystroke would trip the shared 20-reads-per-60s window — typing must stay local")


def test_the_committed_query_asks_the_worker():
    page = search_page()
    enter = handler_body(page, "q", "keydown")
    assert "runServerSearch(" in enter, "Enter is a committed query and must reach the server ranking"
    # A deep link (`/search/?q=…`) is the same commitment, so it takes the same path.
    start = page.index("async function init()")
    end = page.index("document.querySelectorAll('[data-lang]')", start)   # the *next* one, not line 254's
    init = page[start:end]
    assert "runServerSearch(" in init, "a ?q= deep link must also use the server ranking"


def test_the_server_path_uses_the_api_and_adapts_the_row_shape():
    page = search_page()
    assert "/api/lessons?q=" in page, "the committed query must go to the documented search endpoint"
    assert "toLocalShape" in page, "server rows must be adapted to what the renderer reads"
    assert "row.description" in page, (
        "the API returns `description` where the local rows carry `summary`; the adapter is what bridges them")
    assert "relaxed" in page, (
        "the endpoint relaxes a sentence query to any-term and says so — the page must not drop that")


def test_an_empty_server_answer_keeps_the_local_hits_and_says_so():
    """`no_match` must not blank a page that visibly had results — it explains itself instead."""
    page = search_page()
    assert "showServerNote" in page
    assert "no_match" in page, "the endpoint's no-match flag is what triggers the note"


def test_the_notes_are_present_in_both_languages_without_touching_the_homepage_dictionaries():
    """`docs/locales/*.json` is the homepage's surface (its gate fails any key the homepage does not
    reach), so this page carries its own map — and it must cover both languages, or a zh reader gets
    English copy on a page whose other strings are translated."""
    page = search_page()
    for lang in ("en", "zh"):
        assert re.search(rf"\b{lang}:\s*\{{", page), f"the notes map has no {lang} entry"
    for kind in ("ranked", "relaxed", "noMatch"):
        assert page.count(f"{kind}:") >= 2, f"{kind} must exist in both languages"
    # …and the dictionaries stay the homepage's: this page's keys are not in them.
    for lang in ("en", "zh"):
        dictionary = json.loads((REPO / "docs" / "locales" / f"{lang}.json").read_text(encoding="utf-8"))
        for key in ("serverRanked", "serverRelaxed", "serverNoMatch"):
            assert key not in dictionary, (
                f"{key} was added to {lang}.json, whose gate requires the homepage to reach every key")
