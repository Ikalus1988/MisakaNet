#!/usr/bin/env python3
"""The homepage's registration timeline must not fan out one request per registration.

Measured 2026-09-24 from the zone's own analytics (cf-diagnostics run 5, 72h window): ~2,700 HTTP 504s
and ~2,920 401s, concentrated on `/api/github/repos/…/issues/NNN/comments` — and every one of those
paths was fetched by this page. `loadRecentRegistrations()` listed up to 100 registration issues and
then fetched each issue's comments **in parallel** to read its node number, on every page load,
through one worker:

    const nodeFetches = displayIssues.map(async (issue) => {
      const comments = await fetchJSON(proxyGithubUrl(issue.comments_url));
      …

The burst outran both the worker's upstream budget and GitHub's secondary rate limits, and the page
renders **six** rows (the rest is a collapsed `<details>`). The fix is a bounded pool
(`collectNodeNumbers`, `NODE_LOOKUP_CONCURRENCY`) with the visible rows first and the remainder on a
deferred pass.

These rules are pure functions over the page source so the fixtures can prove each one fires — a rule
that cannot go red is not a rule.
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
INDEX = REPO / "docs" / "index.html"

# The shape that caused it, as a literal: one async fetch per registration, unbounded.
UNBOUNDED_FANOUT = "displayIssues.map(async"


def number_after(page: str, prefix: str) -> int | None:
    """The integer that follows `prefix` — scanning, not regex.

    CodeQL flagged `re.search(r"...\\s*\\{...")` in a sibling test file twice (alert #281,
    `py/polynomial-redos`), and the shape it objects to is an unbounded quantifier followed by a
    literal. Reading a constant needs no quantifier at all.
    """
    if prefix not in page:
        return None
    tail = page.split(prefix, 1)[1]
    digits = ""
    for ch in tail:
        if ch.isdigit():
            digits += ch
        elif digits:
            break
        elif ch != " ":
            return None
    return int(digits) if digits else None


def awaited_fetch_inside_a_loop(page: str) -> bool:
    """`for (…) … of …) { … await fetch … }` — scanned by hand, for the same reason."""
    at = page.find("for (")
    while at != -1:
        window = page[at:at + 400]
        if " of " in window.split(")", 1)[0] and "await fetch" in window:
            return True
        at = page.find("for (", at + 1)
    return False


def fanout_problems(page: str) -> list[str]:
    problems = []
    if UNBOUNDED_FANOUT in page:
        problems.append(
            "the registration loader maps `displayIssues` into async fetches — one request per "
            "registration (up to 100), which is the burst that produced ~2,700 504s. Use "
            "collectNodeNumbers()"
        )
    if number_after(page, "const NODE_LOOKUP_CONCURRENCY = ") is None:
        problems.append(
            "no NODE_LOOKUP_CONCURRENCY constant: the comment lookup is unbounded again, or the pool "
            "was deleted and the count is now implicit somewhere else"
        )
    if "async function collectNodeNumbers(" not in page:
        problems.append("collectNodeNumbers() is gone — the bounded pool is what keeps this in line")
    if awaited_fetch_inside_a_loop(page):
        problems.append(
            "an awaited fetch inside a `for … of` loop: sequential is safe for the *count* but this "
            "page shows six rows and fetches up to a hundred, so make the bound explicit instead"
        )
    return problems


def preload_problems(page: str) -> list[str]:
    problems = []
    if "NODE_LOOKUP_PRELOAD" not in page:
        problems.append("nothing bounds the first paint: the loader may be waiting for every issue")
    # Scan *every* deferred call, not the first one in the file: the page has several `setTimeout`
    # calls, and taking the first made this rule depend on their order.
    deferred = False
    at = page.find("setTimeout(")
    while at != -1:
        if "collectNodeNumbers(" in page[at:at + 240]:
            deferred = True
            break
        at = page.find("setTimeout(", at + 1)
    if not deferred:
        problems.append(
            "the remainder is no longer deferred, so first paint waits on ~100 requests again"
        )
    if "const DISPLAY_LIMIT = 6;" not in page:
        problems.append("the rendered-row limit moved; the preload constant is sized against it")
    return problems


@pytest.fixture(scope="module")
def page() -> str:
    return INDEX.read_text(encoding="utf-8")


def test_the_registration_loader_is_bounded_and_deferred(page: str) -> None:
    problems = fanout_problems(page) + preload_problems(page)
    assert not problems, "\n  - ".join(problems)


def test_the_preload_matches_what_the_page_renders(page: str) -> None:
    """A preload smaller than the visible list would render placeholder numbers on first paint."""
    preload = number_after(page, "const NODE_LOOKUP_PRELOAD = ")
    display = number_after(page, "const DISPLAY_LIMIT = ")
    concurrency = number_after(page, "const NODE_LOOKUP_CONCURRENCY = ")
    assert preload is not None and display is not None and concurrency is not None, "constants moved"
    assert preload >= display, (
        f"NODE_LOOKUP_PRELOAD={preload} < DISPLAY_LIMIT={display}: the visible rows would rely on the "
        "counter fallback instead of their real node numbers"
    )
    assert 1 <= concurrency <= 8, f"NODE_LOOKUP_CONCURRENCY={concurrency} is not a bound"


# ── fixtures: proof that each rule can go red ────────────────────────────────────────────────────

def test_the_unbounded_shape_is_caught():
    """The exact code that produced the burst, as it stood before 2026-09-24."""
    old = """
    const nodeFetches = displayIssues.map(async (issue) => {
      const comments = await fetchJSON(proxyGithubUrl(issue.comments_url));
      return comments;
    });
    """
    problems = fanout_problems(old)
    assert any("displayIssues" in p for p in problems), problems


def test_a_missing_pool_is_caught():
    problems = fanout_problems("const NODE_LOOKUP_CONCURRENCY = 3;\n")
    assert any("collectNodeNumbers" in p for p in problems), problems


def test_an_undeferred_remainder_is_caught():
    page = "const NODE_LOOKUP_PRELOAD = 6;\nconst DISPLAY_LIMIT = 6;\ncollectNodeNumbers(rest, into);"
    problems = preload_problems(page)
    assert any("deferred" in p for p in problems), problems


def test_a_preload_smaller_than_the_visible_list_is_caught():
    page = INDEX.read_text(encoding="utf-8").replace(
        "const NODE_LOOKUP_PRELOAD = 6;", "const NODE_LOOKUP_PRELOAD = 1;")
    assert number_after(page, "const NODE_LOOKUP_PRELOAD = ") < number_after(page, "const DISPLAY_LIMIT = ")
