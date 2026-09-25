#!/usr/bin/env python3
"""The homepage must not fan out one request per registration — and now it makes none at all.

Measured 2026-09-24 from the zone's own analytics (cf-diagnostics run 5, 72h window): ~2,700 HTTP 504s
and ~2,920 401s, concentrated on `/api/github/repos/…/issues/NNN/comments` — and every one of those
paths was fetched by this page. `loadRecentRegistrations()` listed up to 100 registration issues and
then fetched each issue's comments **in parallel** to read its node number, on every page load,
through one worker:

    const nodeFetches = displayIssues.map(async (issue) => {
      const comments = await fetchJSON(proxyGithubUrl(issue.comments_url));
      …

#2151 bounded that (a pool of 3, the visible rows first, the rest deferred). Then 2026-09-24 **deleted
the section**: its count was registration-labelled issues capped at 100 — neither nodes nor members —
rendered under a heading called "最近注册记录" beneath a nav item called "Agent nodes", and it was the
page's only reason to have a request budget at all. What replaced it is a static snapshot
(`docs/data/activity.json`, written by `scripts/sync_site_activity.py`).

So this gate has moved from "the fan-out is bounded" to "there is no fan-out" — the stronger property,
and the one worth keeping. What a future edit has to satisfy is that **no loader on this page issues a
request per item** and that nothing below the fold is on the first paint's path. The rules are pure
functions over the page source so the fixtures can prove each one fires; a rule that cannot go red is
not a rule.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
INDEX = REPO / "docs" / "index.html"

# The machinery of the removed section, by name. Any of these coming back means the per-issue request
# budget came back with it.
DELETED = ("loadRecentRegistrations", "collectNodeNumbers", "NODE_LOOKUP_CONCURRENCY",
           "displayIssues", "comments_url", "labels=registration", "recent-list")

# The panels that must all be started from the one deferral.
DEFERRED_LOADERS = ("loadContributors()", "loadLatestUpdates()", "loadActivity()")


def uncommented(page: str) -> str:
    """The page with its comments removed: these assertions are about code, not prose.

    Learned the hard way — a sibling gate failed on its own explanation, because the comment
    documenting a removed shape quotes that shape.
    """
    text = re.sub(r"<!--.*?-->", "", page, flags=re.S)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?<!:)//[^\n]*", "", text)


def mapping_lines(page: str) -> list[str]:
    """Lines that turn a collection into requests. One is enough to be a fan-out."""
    hits = []
    for number, line in enumerate(page.splitlines(), 1):
        if ".map(async" in line:
            hits.append(f"{number}: {line.strip()[:110]}")
        elif re.search(r"\.map\(\s*(?:async\s*)?\(?[^)]*\)?\s*=>.*\bfetch", line):
            hits.append(f"{number}: {line.strip()[:110]}")
    return hits


def awaited_fetch_inside_a_loop(page: str) -> bool:
    """`for (…) … of …) { … await fetch … }` — scanned by hand, not by regex.

    CodeQL flagged `re.search(r"...\\s*\\{...")` in a sibling test file twice (alert #281,
    `py/polynomial-redos`), and the shape it objects to is an unbounded quantifier followed by a
    literal.
    """
    at = page.find("for (")
    while at != -1:
        window = page[at:at + 400]
        if " of " in window.split(")", 1)[0] and "await fetch" in window:
            return True
        at = page.find("for (", at + 1)
    return False


def fanout_problems(page: str) -> list[str]:
    problems = []
    if mapping_lines(page):
        problems.append(
            "a `.map(…) => fetch(…)` over a collection is back — that is one request per item, the "
            "shape behind ~2,700 504s: " + "; ".join(mapping_lines(page))
        )
    if awaited_fetch_inside_a_loop(page):
        problems.append(
            "an awaited fetch inside a `for … of` loop: sequential is still one request per item, and "
            "the page's remaining loaders are single bounded requests by design"
        )
    still_here = [name for name in DELETED if name in page]
    if still_here:
        problems.append(
            f"the removed registration section is back in some form: {still_here}. Deleting it was "
            f"the point — its count was registration-labelled issues capped at 100"
        )
    return problems


def deferral_problems(page: str) -> list[str]:
    problems = []
    if "const PANEL_DEFER_MS = " not in page:
        problems.append("the single deferral constant is gone; below-the-fold panels may block paint")
        return problems
    at = page.find("PANEL_DEFER_MS)")
    if at == -1:
        problems.append("PANEL_DEFER_MS is declared and never used — the panels are not deferred")
        return problems
    window = page[at - 400:at]
    if "setTimeout(" not in window:
        problems.append("the panels are no longer started from inside a setTimeout")
    for loader in DEFERRED_LOADERS:
        if loader not in window:
            problems.append(f"{loader} is no longer deferred with the others")
    return problems


@pytest.fixture(scope="module")
def page() -> str:
    return uncommented(INDEX.read_text(encoding="utf-8"))


# ── the live page ────────────────────────────────────────────────────────────────────────────────

def test_the_page_makes_no_per_item_requests(page: str) -> None:
    problems = fanout_problems(page)
    assert not problems, "\n  - ".join(problems)


def test_nothing_below_the_fold_blocks_the_first_paint(page: str) -> None:
    problems = deferral_problems(page)
    assert not problems, "\n  - ".join(problems)


def request_targets(page: str) -> list[str]:
    """Every request target on the page, `fetch` and `fetchJSON` alike."""
    return [target.strip() for target in
            re.findall(r"""(?<![A-Za-z])(?:fetchJSON|fetch)\(([^()]*(?:\([^()]*\))?[^()]*)\)""", page)]


def test_every_request_target_is_same_origin_and_readable(page: str) -> None:
    """Bounded is not the same as *legible*: what matters is that a person can read every network
    call this page makes, and that none of them leaves the origin on its own.

    `GET /mcp` is advertised as the interface; a homepage that quietly calls third parties would
    undercut that, and the page is small enough that the whole surface fits in one list.
    """
    targets = request_targets(page)
    assert targets, "no request targets found — did the loaders change shape?"
    assert len(targets) <= 14, f"more targets than a reviewer can hold: {targets}"
    off_origin = [t for t in targets if re.search(r"https?://", t)]
    assert not off_origin, f"off-origin request(s): {off_origin}"


def test_the_only_interpolated_github_path_is_the_single_registration_poll(page: str) -> None:
    """A path that interpolates a *collection* is a fan-out waiting to happen.

    The one allowed interpolation is `issues/${data.issue_number}/comments` — the post-registration
    poll for the visitor's own new issue, bounded to 18 attempts over 3 minutes (`maxPolls`). The
    fan-out that produced ~2,700 504s interpolated a value taken from a list of up to 100 issues,
    which is the difference this rule holds.
    """
    interpolated = set()
    for path in re.findall(r"\$\{GITHUB_PROXY\}[^`\n]*", page):
        interpolated |= set(re.findall(r"\$\{([^}]+)\}", path))
    interpolated -= {"GITHUB_PROXY"}  # the origin, not a path segment
    assert interpolated <= {"data.issue_number"}, (
        f"the GitHub proxy path interpolates {sorted(interpolated)}; only the single-registration poll "
        f"may interpolate, because anything list-shaped here is one request per item"
    )
    assert "data.issue_number" in interpolated, "the registration poll moved — update this rule"


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
    assert any("map(" in p for p in problems), problems
    assert any("displayIssues" in p for p in problems), problems


def test_a_sequential_per_item_loop_is_caught():
    problems = fanout_problems("for (const issue of issues) { await fetch(issue.url); }")
    assert any("awaited fetch inside" in p for p in problems), problems


def test_a_reintroduced_section_is_caught():
    problems = fanout_problems("async function loadRecentRegistrations() { /* … */ }")
    assert any("loadRecentRegistrations" in p for p in problems), problems


def test_an_undeferred_panel_is_caught():
    """Declared but unused, and called outside a `setTimeout`: both are "not deferred"."""
    for source in ("const PANEL_DEFER_MS = 1200;\nloadActivity();",
                   "const PANEL_DEFER_MS = 1200;\nqueueMicrotask(loadActivity, PANEL_DEFER_MS);"):
        problems = deferral_problems(source)
        assert problems, source
        assert any("defer" in p or "setTimeout" in p for p in problems), problems


def test_a_panel_dropped_from_the_deferral_is_caught():
    problems = deferral_problems(
        "const PANEL_DEFER_MS = 1200;\nsetTimeout(() => { loadContributors(); }, PANEL_DEFER_MS);"
    )
    assert any("loadActivity" in p for p in problems), problems
