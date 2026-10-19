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
import subprocess
from pathlib import Path

import pytest

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


# ── a degraded read is not "0 results" (issue #3511) ──────────────────────────────────────────────
#
# Measured 2026-10-18 with D1's quota spent: the backend answered out of a frozen snapshot and this
# page printed its confident zero ("没有精确匹配" / "Found 0 lessons") — for a read the search answer
# itself marks `degraded: true`, with `degraded_reasons` and a `notice` saying it is "not proof that
# no lesson exists". The rule is the panel's, restated for a page: a degraded backend renders
# "结果可能不完整（原因）", never the zero.

#: The pre-fix bytes, by commit and never by branch: the `main` tip this change was cut from.
DEGRADED_PRE_FIX_SHA = "4b4b21da6d9ed97b02f9908f160cc8948c7d4429"


def _zero_branch(page: str) -> str:
    """The body of `render()`'s `if (!results.length)` block — where the confident zero is printed."""
    start = page.index("if (!results.length) {")
    return page[start:page.index("const searchable", start)]


def _degraded_label_problems(page: str) -> list[str]:
    problems: list[str] = []
    if "degradedLabel" not in page:
        return ["the page declares no degraded label, so a degraded read has nothing to be labelled with"]
    labels = re.findall(r"degradedLabel:\s*'([^']*)'", page)
    if not any("结果可能不完整（{reason}）" == label for label in labels):
        problems.append("the zh label is not the acceptance sentence 结果可能不完整（原因）: " + repr(labels))
    if not any("Results may be incomplete ({reason})" == label for label in labels):
        problems.append("the en label is missing or reworded beyond translation: " + repr(labels))

    zero = _zero_branch(page)
    if "t('degradedLabel'" not in zero and 't("degradedLabel"' not in zero:
        problems.append("the zero-result block never uses the degraded label — a degraded read renders "
                        "as the confident zero")
    # The headline must be decided by the degradation, not printed alongside the zero.
    if not re.search(r"degraded\s*\?\s*t\(['\"]degradedLabel['\"]", zero):
        problems.append("the zero-result headline is not chosen by the degraded state: " + repr(zero[:160]))
    if "degradedState" not in page:
        problems.append("nothing classifies the answer as degraded, so the label can never fire")
    # The committed query must pass the classification into the render, or the label is dead code.
    if not re.search(r"render\(\[\],\s*q,\s*\{\s*degraded\s*\}\)", page):
        problems.append("runServerSearch does not render the labelled zero state for a degraded empty answer")
    return problems


def test_a_degraded_backend_is_labelled_incomplete_not_zero():
    """The regression test: fails whenever a degraded read can render as zero/empty without a label."""
    page = search_page()
    assert _degraded_label_problems(page) == [], _degraded_label_problems(page)


def test_the_degraded_label_gate_can_go_red(tmp_path):
    """A gate nobody has seen fail. The pinned pre-fix bytes and one mutation both must trip it."""
    showed = subprocess.run(["git", "show", f"{DEGRADED_PRE_FIX_SHA}:docs/search/index.html"],
                            cwd=REPO, capture_output=True, text=True, timeout=60)
    if showed.returncode != 0:
        pytest.skip("the pre-fix fixture did not run: this clone does not carry " + DEGRADED_PRE_FIX_SHA[:12]
                    + ". Run `git fetch origin " + DEGRADED_PRE_FIX_SHA + "` to replay the red proof.")
    assert "degradedLabel" not in showed.stdout, (
        f"{DEGRADED_PRE_FIX_SHA[:12]} already carries the degraded label, so it cannot replay its "
        "absence; pick the commit before the change and update DEGRADED_PRE_FIX_SHA")
    assert _degraded_label_problems(showed.stdout) != [], (
        "the pre-fix bytes pass this rule, so it does not test the change")

    # The specific failure the issue names: the zero block prints the confident zero again.
    page = search_page()
    mutated = page.replace(
        "const headline = degraded\n      ? t('degradedLabel', { reason: degraded.reason })\n"
        "      : t('noMatchPrefix') + ' \"' + escapeHTML(q) + '\". ' + t('noMatchSuffix');",
        "const headline = t('noMatchPrefix') + ' \"' + escapeHTML(q) + '\". ' + t('noMatchSuffix');")
    assert mutated != page, "the mutation did not take — update it with the copy"
    broken = tmp_path / "search-index.html"
    broken.write_text(mutated, encoding="utf-8")
    assert _degraded_label_problems(mutated) != [], (
        "a zero block that dropped the degraded label passed the rule")
