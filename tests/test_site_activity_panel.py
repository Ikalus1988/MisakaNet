#!/usr/bin/env python3
"""The homepage's activity panel must describe what it counts, and must not be able to be slow.

This panel replaced the registrations timeline (2026-09-24), and both halves of that decision are
gated here rather than remembered.

**What it counts.** The timeline's number was registration-labelled GitHub issues, capped at 100,
rendered under a heading called "最近注册记录" beneath a nav item called "Agent nodes" — three names
for one thing, none of them what the number was. The failure was not the number, it was the label:
`recentNodesNote` claimed "self-declared · not identity" about a *count*, and the stats card above it
said "已注册节点" in Chinese and "Active Nodes" in English for a monotonic allocation counter that
neither language described — then wore the honest label for two days before the number itself was
dropped. So this file pins the label-to-number correspondence on both sides:

* the class list the page renders is the class list the snapshot publishes
  (`scripts/sync_site_activity.py`), and every class has a label in both dictionaries;
* the date shown is the *snapshot's* date, never the word "today" — a stale file has to look stale
  instead of claiming currency it does not have;
* the node counter is **not** rendered, and neither is the "agent contributors" count that sat
  next to it: one is a monotonic allocation counter, the other counts an optional self-declared
  header, and no label makes either a stat worth showing (2026-09-26).

**How it is fed.** `/api/analytics/traffic` answers in 0.66–0.75s from cache and **17.4s** when it
recomputes (five consecutive requests, 2026-09-24). A browser panel calling it would rebuild the 504
generator that #2151 spent a day removing, so the panel reads `docs/data/activity.json` and the live
endpoint must not appear on this page at all.
"""
from __future__ import annotations

import json
import pathlib
import re

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
INDEX = REPO / "docs" / "index.html"
LOCALES = {lang: REPO / "docs" / "locales" / f"{lang}.json" for lang in ("en", "zh")}
SCRIPT = REPO / "scripts" / "sync_site_activity.py"

# The file the panel reads, and the endpoint it must never read.
SNAPSHOT_PATH = "data/activity.json"
LIVE_ENDPOINT = "/api/analytics/traffic"

# The node counter must be rendered from `counter.current`; this is the subtraction that used to turn
# it into a population it is not.
# `counter.current` adjusted by a constant — with or without the closing paren that `animateCounter(…)`
# puts between them (the first version of this pattern required them adjacent, and the mutation that
# re-introduced the subtraction survived it).
SUBTRACTION = re.compile(r"counter\.current\b[^;\n]*?[-+]\s*\d+")


@pytest.fixture(scope="module")
def page() -> str:
    return INDEX.read_text(encoding="utf-8")


def locale(lang: str) -> dict[str, str]:
    return json.loads(LOCALES[lang].read_text(encoding="utf-8"))


def uncommented(page: str) -> str:
    """The page with its comments removed.

    Every assertion in this file is about what the page *renders*, and a source scan cannot tell
    markup from prose. The first draft of these gates failed on its own explanation: the comment
    documenting the fix quotes the old label ("registered nodes" / "Active Nodes") and the old
    expression, so the assertion that the label is gone was defeated by the note saying it was gone.
    A gate that the documentation of the fix can flip is not a gate.
    """
    without_html = re.sub(r"<!--.*?-->", "", page, flags=re.S)
    without_css = re.sub(r"/\*.*?\*/", "", without_html, flags=re.S)
    # `//` at the end of a line, but not the `//` in `https://`.
    return re.sub(r"(?<!:)//[^\n]*", "", without_css)


def panel(page: str) -> str:
    """The `#activity-body` container and the loader that fills it, as one string."""
    at = page.index('id="activity-body"')
    start = page.rindex("<div", 0, at)
    return page[start:start + 400] + page[page.index("async function loadActivity()"):
                                          page.index("async function loadLatestUpdates()")]


def rendered_classes(page: str) -> set[str]:
    """The classes the page wires up, from its own table.

    `ACTIVITY_CLASSES` is `[['mcp', 'activityClassMcp'], …]`; the keys are interpolated into
    `data-i18n`, so the table — not the markup — is where the contract lives.
    """
    match = re.search(r"const ACTIVITY_CLASSES = \[(.*?)\n\];", page, re.S)
    assert match, "ACTIVITY_CLASSES moved; fix this gate rather than deleting it"
    return set(re.findall(r"\['([a-z-]+)',", match.group(1)))


# ── the data contract ────────────────────────────────────────────────────────────────────────────

def test_the_page_renders_exactly_the_classes_the_snapshot_publishes():
    """Two lists, one number: a class in only one of them is a figure that disappears silently."""
    import sys

    sys.path.insert(0, str(REPO / "scripts"))
    import sync_site_activity  # noqa: PLC0415

    assert rendered_classes(INDEX.read_text(encoding="utf-8")) == set(sync_site_activity.CALL_CLASSES)


def test_every_class_has_a_label_in_both_dictionaries(page):
    keys = re.findall(r"\['([a-z-]+)', '([A-Za-z]+)'\]", page)
    assert keys, "the class table no longer carries locale keys"
    for _, key in keys:
        for lang in ("en", "zh"):
            assert key in locale(lang), f"{lang}.json has no {key}"


def test_the_committed_snapshot_satisfies_the_panel():
    """The file the panel reads is committed, so its shape is checked with everything else."""
    snapshot = json.loads((REPO / "docs" / SNAPSHOT_PATH).read_text(encoding="utf-8"))
    assert set(snapshot) == {"generated_at", "source", "date", "total", "calls"}
    assert set(snapshot["calls"]) == rendered_classes(INDEX.read_text(encoding="utf-8"))


# ── it cannot be slow ────────────────────────────────────────────────────────────────────────────

def test_the_panel_never_calls_the_live_endpoint(page):
    """The 17.4-second cold path, measured — a browser must not be able to reach it."""
    assert LIVE_ENDPOINT not in uncommented(page), (
        f"the page calls {LIVE_ENDPOINT}, whose recompute takes 17.4s; read "
        f"{SNAPSHOT_PATH} instead (scripts/sync_site_activity.py)"
    )


def test_the_panel_reads_the_static_snapshot(page):
    assert f'const ACTIVITY_URL = "{SNAPSHOT_PATH}"' in page, "the panel's data source moved"
    assert "fetchJSON(ACTIVITY_URL)" in panel(page), "the panel no longer reads ACTIVITY_URL"


def test_the_panel_loads_after_first_paint(page):
    """Nothing below the fold may sit on the critical path — the rule the fan-out fix established."""
    code = uncommented(page)
    at = code.index("PANEL_DEFER_MS)")
    window = code[at - 400:at]
    assert "setTimeout(" in window, "the panels are no longer deferred"
    assert "loadActivity()" in window, "loadActivity is no longer among the deferred loaders"


def test_the_page_carries_no_per_issue_fetch_loop(page):
    """The shape that produced ~2,700 504s, asserted at zero rather than at a small bound."""
    code = uncommented(page)
    for shape in ("displayIssues", "collectNodeNumbers", "comments_url", "labels=registration"):
        assert shape not in code, f"{shape} is back — the registration fan-out was deleted, not bounded"


# ── what the panel and the card claim ────────────────────────────────────────────────────────────

def test_the_snapshot_date_is_rendered_rather_than_the_word_today(page):
    """A snapshot can be stale; claiming "today" would hide it. The date comes from the file."""
    body = panel(page)
    assert "{ date:" in body and "snap.date" in body, "the panel no longer passes the snapshot's date"
    for claim in (">Today<", ">today<", "updated just now"):
        assert claim not in body, f"the panel claims {claim!r} without reading a date"


def test_the_panel_says_what_its_numbers_are(page):
    """The honesty note the timeline carried in the same slot, kept for the same reason."""
    assert 'data-i18n="activityNote"' in page
    note = {"en": locale("en")["activityNote"], "zh": locale("zh")["activityNote"]}
    assert "aggregate" in note["en"] and "no identity" in note["en"], note
    assert "聚合" in note["zh"] and "不含身份" in note["zh"], note


def test_the_node_counter_is_not_published_as_a_stat(page):
    """The number is gone from the card, and the fix is not another label (2026-09-26).

    Two earlier rounds kept the number and corrected its name ("registered nodes" / "Active Nodes" →
    "node IDs issued"). Both were true and neither was enough: `counter.current` is a monotonic
    **allocation** counter that node IDs are handed out from — nothing comes off it, and an anonymous
    caller gets a fresh node per call — so it grows with our own automation and cannot describe usage
    however it is labelled. The card now shows no node count at all; what is used is the
    network-activity panel (MCP calls, split by class), which counts requests rather than identities.

    The subtraction check stays: if the number ever comes back, `current - 10000` must not come back
    with it as a "population".
    """
    assert not SUBTRACTION.search(uncommented(page)), (
        "the node counter is being adjusted again; it is a monotonic allocation counter, so any "
        "derived figure would need a label saying which figure it is"
    )
    assert 'id="total-nodes"' not in page, "the node stat is rendered again"
    code = uncommented(page)
    assert "registered nodes" not in code and "Active Nodes" not in code
    for lang in ("en", "zh"):
        dictionary = locale(lang)
        for dead in ("statLatest", "statNodes"):
            assert dead not in dictionary, (
                f"{lang}.json still carries {dead!r} — a label for a number the page no longer "
                "renders is the correct wording sitting next to a wrong one, which is how the last "
                "round shipped"
            )


def test_the_agent_contributor_count_is_not_published_as_a_stat(page):
    """The other half of the same decision (2026-09-26): a count of self-declared agents, gone.

    It sat next to the node counter and read `sorted.filter(... agentClass !== '' && !== 'human').length`
    over the contributor wall — rows that carry an `Agent-Type:` header, minus a client-side list of
    owner logins. `agent_type` is self-reported and unverified (`AGENTS.md` §3.3), and the header is
    optional, so the number measured who remembered to write one rather than how many agents
    contribute. The wall below already lists the contributors with their contributions.

    The assertion is on the *published stat*, not on the wall: the wall's own count stays, because it
    counts rows the page renders and a reader can check each one by hand.
    """
    assert 'id="agent-contrib-count"' not in page, "the agent-contributor stat is rendered again"
    assert "agent contributors" not in uncommented(page)
    for lang in ("en", "zh"):
        assert "statAgents" not in locale(lang), (
            f"{lang}.json still carries statAgents — a label for a stat the card no longer renders"
        )
    # The wall keeps its heading and its own row count; only the headline number is gone.
    for lang in ("en", "zh"):
        assert "contribSection" in locale(lang), f"the contributor wall's heading must stay ({lang})"
    assert 'id="contrib-count"' in page and 'data-i18n="contribSection"' in page, (
        "the contributor wall itself must still render — this test removes a headline stat, not the list"
    )


def test_the_registration_success_panel_still_gets_a_counter_to_estimate_from(page):
    """Deleting the timeline nearly took this with it.

    The success panel predicts the visitor's node number from `CURRENT_COUNTER + 1` when the worker
    returns none. `CURRENT_COUNTER` is assigned inside `loadStats()` for the panel's benefit only; a
    deletion that removed the assignment as "dead" would freeze the prediction, and this is the one
    number a visitor reads back about *themselves*.

    2026-09-28 changed what an unusable counter means. It used to be seeded with a constant (10010)
    and refreshed with `Number(counter.current) || CURRENT_COUNTER`, so an unavailable endpoint still
    produced a number — from a default or from whatever was read last. `/api/counter` lost its file
    fallback that day (the mirror could be months old; issue #1820), so the page now treats "no value"
    as a state: `null`, and the panel prints no id at all rather than a wrong one. Both halves are
    pinned here, because either alone is a regression: a constant seed, or a `||` that turns
    `Number(null) === 0` back into a number.
    """
    code = uncommented(page)
    assert "CURRENT_COUNTER + 1" in code, "the success panel's prediction moved"
    assert re.search(r"CURRENT_COUNTER = Number\.isFinite\(readCounter\)[^;]*\? readCounter : null", code), (
        "CURRENT_COUNTER is no longer refreshed from the counter, or no longer distinguishes "
        "'no value' from a value — the success panel would print a node id it never read"
    )
    assert re.search(r"let CURRENT_COUNTER = null;", code), (
        "CURRENT_COUNTER is seeded with a constant again: an unavailable counter would then predict a "
        "node id from that constant"
    )
    assert re.search(r"const readCounter = counter \? Number\(counter\.current\) : NaN;", code), (
        "the counter read no longer coerces explicitly — `Number(null)` is 0, so a null payload must "
        "not travel through a bare Number() into CURRENT_COUNTER"
    )
    # The prediction itself: a number only when the counter was read, `null` otherwise. This is the
    # line the whole change is about — `data.node_number || (CURRENT_COUNTER + 1)` needs a
    # `CURRENT_COUNTER` that is never a stand-in.
    assert re.search(
        r"const estimatedNode = Number\(data\.node_number\)\s*"
        r"\|\|\s*\(CURRENT_COUNTER === null \? null : CURRENT_COUNTER \+ 1\);",
        code,
    ), (
        "the success panel's prediction no longer distinguishes 'no counter value' from a value — it "
        "would print a node id derived from a number this page never read"
    )
    assert "regNodeLineNoNumber" in code, (
        "the no-number branch lost its own wording — the panel would reuse 'estimated #...' for a "
        "number it does not have"
    )
