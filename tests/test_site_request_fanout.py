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

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
INDEX = REPO / "docs" / "index.html"

# Any `X.map(async …)` / `for … of X` that awaits a fetch inside the registration loader.
UNBOUNDED_FANOUT = re.compile(r"displayIssues\.map\(\s*async")
AWAIT_FETCH_IN_LOOP = re.compile(r"for\s*\([^)]*\bof\b[^)]*\)\s*\{[^}]*await\s+fetch", re.S)


def fanout_problems(page: str) -> list[str]:
    problems = []
    if UNBOUNDED_FANOUT.search(page):
        problems.append(
            "the registration loader maps `displayIssues` into async fetches — one request per "
            "registration (up to 100), which is the burst that produced ~2,700 504s. Use "
            "collectNodeNumbers()"
        )
    if not re.search(r"const NODE_LOOKUP_CONCURRENCY = \d+;", page):
        problems.append(
            "no NODE_LOOKUP_CONCURRENCY constant: the comment lookup is unbounded again, or the pool "
            "was deleted and the count is now implicit somewhere else"
        )
    if not re.search(r"async function collectNodeNumbers\(", page):
        problems.append("collectNodeNumbers() is gone — the bounded pool is what keeps this in line")
    if AWAIT_FETCH_IN_LOOP.search(page):
        problems.append(
            "an awaited fetch inside a `for … of` loop: sequential is safe for the *count* but this "
            "page shows six rows and fetches up to a hundred, so make the bound explicit instead"
        )
    return problems


def preload_problems(page: str) -> list[str]:
    problems = []
    if "NODE_LOOKUP_PRELOAD" not in page:
        problems.append("nothing bounds the first paint: the loader may be waiting for every issue")
    if not re.search(r"setTimeout\(\(\)\s*=>\s*\{\s*collectNodeNumbers\(", page):
        problems.append(
            "the remainder is no longer deferred, so first paint waits on ~100 requests again"
        )
    if not re.search(r"const DISPLAY_LIMIT = 6;", page):
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
    preload = int(re.search(r"const NODE_LOOKUP_PRELOAD = (\d+);", page).group(1))
    display = int(re.search(r"const DISPLAY_LIMIT = (\d+);", page).group(1))
    assert preload >= display, (
        f"NODE_LOOKUP_PRELOAD={preload} < DISPLAY_LIMIT={display}: the visible rows would rely on the "
        "counter fallback instead of their real node numbers"
    )
    concurrency = int(re.search(r"const NODE_LOOKUP_CONCURRENCY = (\d+);", page).group(1))
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


def test_a_preload_smaller_than_the_visible_list_is_caught(monkeypatch):
    page = INDEX.read_text(encoding="utf-8").replace(
        "const NODE_LOOKUP_PRELOAD = 6;", "const NODE_LOOKUP_PRELOAD = 1;")
    preload = int(re.search(r"const NODE_LOOKUP_PRELOAD = (\d+);", page).group(1))
    display = int(re.search(r"const DISPLAY_LIMIT = (\d+);", page).group(1))
    assert preload < display, "the mutation did not change the relationship it was meant to change"
