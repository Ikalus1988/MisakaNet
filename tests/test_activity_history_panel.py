#!/usr/bin/env python3
"""The activity trend's chart must not be able to show a lie either — and must be able to show nothing.

`tests/test_site_activity_panel.py` owns the headline (one day). This file owns the week underneath
it (issue #2521): seven bars of **our own** daily call counters. A chart has one failure mode a
number does not — it draws a *shape*, so a hole becomes a slope and a flat zero week becomes a
quiet-looking period — and one advantage: "no chart" is a readable state, which is what the panel
renders when it has no series.

What is gated here:

* the chart's only sources are the anonymous history route and the file
  `scripts/sync_activity_series.py` writes — never `/api/analytics/traffic`, whose body varies by
  caller and must not be read by a public page;
* there are no numbers in the page itself. The bars come from a payload with a writer on both ends
  (the route's counters, the script's file); a hardcoded series would be a screenshot, not a panel;
* an undrawable series is drawn as nothing: an all-zero week is refused here exactly as it is
  refused by the writer and by the route;
* the copy names what these numbers are **not** (Cloudflare edge metrics) in both languages, and the
  newest bar is marked as the day in progress rather than drawn as a finished one;
* the trend is loaded after the numbers and cannot take them down with it.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
INDEX = REPO / "docs" / "index.html"
LOCALES = {lang: REPO / "docs" / "locales" / f"{lang}.json" for lang in ("en", "zh")}
sys.path.insert(0, str(REPO / "scripts"))

HISTORY_ROUTE = "/api/activity/history"
SERIES_SNAPSHOT_PATH = "data/activity-series.json"
# The per-caller endpoint the panel must never read (see tests/test_site_activity_panel.py).
LIVE_ENDPOINT = "/api/analytics/traffic"


@pytest.fixture(scope="module")
def page() -> str:
    return INDEX.read_text(encoding="utf-8")


def locale(lang: str) -> dict[str, str]:
    return json.loads(LOCALES[lang].read_text(encoding="utf-8"))


def uncommented(page: str) -> str:
    without_html = re.sub(r"<!--.*?-->", "", page, flags=re.S)
    without_css = re.sub(r"/\*.*?\*/", "", without_html, flags=re.S)
    return re.sub(r"(?<!:)//[^\n]*", "", without_css)


def trend_code(page: str) -> str:
    """The trend's own block, marker comment included (the marker *is* the anchor)."""
    at = page.index("// ── Network activity trend")
    end = page.index("async function loadContributors()", at)
    return page[at:end]


def rendered_classes(page: str) -> set[str]:
    match = re.search(r"const ACTIVITY_CLASSES = \[(.*?)\n\];", page, re.S)
    assert match, "ACTIVITY_CLASSES moved; fix this gate rather than deleting it"
    return set(re.findall(r"\['([a-z-]+)',", match.group(1)))


# ── the data contract ────────────────────────────────────────────────────────────────────────────

def test_the_chart_reads_only_its_own_two_sources(page):
    code = trend_code(page)
    sources = uncommented(page)
    assert f'const ACTIVITY_HISTORY_URL = "{HISTORY_ROUTE}' in sources, "the history route moved"
    assert f'const ACTIVITY_HISTORY_SNAPSHOT_URL = "{SERIES_SNAPSHOT_PATH}"' in sources, (
        "the static fallback is gone; a chart with one source is a chart that disappears with it"
    )
    assert "fetchWithTimeout(ACTIVITY_HISTORY_URL" in code, "the live route is no longer read"
    assert "fetchJSON(ACTIVITY_HISTORY_SNAPSHOT_URL)" in code, "the snapshot fallback is no longer read"
    assert code.index("fetchWithTimeout(ACTIVITY_HISTORY_URL") < code.index(
        "fetchJSON(ACTIVITY_HISTORY_SNAPSHOT_URL)"), (
        "the snapshot is fetched before the live route — the fallback became the source"
    )
    assert LIVE_ENDPOINT not in code, (
        f"the chart reads {LIVE_ENDPOINT}, whose body varies by caller and cannot be cached publicly"
    )


def test_the_chart_carries_no_numbers_of_its_own(page):
    """The bars come from a payload with a writer, never from constants in the page.

    The rule the badges and the counts live by (no hand-written numbers in a rendered figure). A
    literal `series: [{date: …, total: …}]` here would be a screenshot that looks like telemetry.
    """
    code = uncommented(trend_code(page))
    assert not re.search(r"total:\s*\d", code), "a count is hardcoded in the page"
    assert not re.search(r"date:\s*['\"]\d{4}-\d{2}-\d{2}", code), "a date is hardcoded in the page"
    assert "activityHistoryMarkup(series" in code, "the renderer no longer takes the payload's series"


def test_the_series_is_held_to_the_writer_s_contract(page):
    """The four classes the writer publishes are the four the chart is fed, in both directions."""
    import sync_site_activity  # noqa: PLC0415  (the day's own writer)
    import sync_activity_series  # noqa: PLC0415

    assert set(sync_activity_series.CALL_CLASSES) == set(sync_site_activity.CALL_CLASSES)
    assert set(sync_activity_series.CALL_CLASSES) == rendered_classes(page)


def test_the_committed_series_if_present_satisfies_the_writer():
    """`docs/data/activity-series.json` is written by the cron; when it exists it must be valid.

    Absent is a designed state (the chart is simply not drawn), so this gate passes on absence and
    fails on a file that would draw a lie — the same judge the writer itself uses, so the two can
    never disagree about what is publishable.
    """
    sys.path.insert(0, str(REPO / "scripts"))
    import sync_activity_series  # noqa: PLC0415

    path = REPO / "docs" / SERIES_SNAPSHOT_PATH
    if not path.is_file():
        pytest.skip(f"{path} is not written yet — the panel draws no chart until the first sync")
    sync_activity_series.validate(json.loads(path.read_text(encoding="utf-8")), where=str(path))


# ── what is drawn, and what is not ───────────────────────────────────────────────────────────────

def test_an_undrawable_series_is_drawn_as_nothing(page):
    """The refusal is the feature: no chart beats a chart that claims the network was idle."""
    code = trend_code(page)
    assert "function activityHistoryValid(" in code, "the reader no longer checks what it draws"
    assert "Array.isArray(series)" in code, "a non-series payload would be drawn as one"
    # The same shape the writer and the route refuse: a series with no non-zero day.
    assert "return any;" in code, "the all-zero refusal is gone — a flat zero week would draw"
    assert "series.length < 2" in code, "a one-point 'trend' would draw as a chart"
    # And the failure path draws nothing rather than an empty chart.
    assert "slot.innerHTML = '';" in code, "the unavailable path now draws something"
    assert "no chart" in code, "the reason for drawing nothing is no longer stated"


def test_the_newest_bar_is_marked_as_the_day_in_progress(page):
    """Today's count is a floor, not a total; drawn as a finished bar it reads as a crash every day."""
    code = trend_code(page)
    assert "is-partial" in code, "the in-progress bar is no longer marked"
    assert "activityTrendPartial" in code, "the marker carries no label a reader can read"
    assert "new Date().toISOString().slice(0, 10)" in code, "the mark no longer knows what today is"


def test_the_copy_says_what_these_numbers_are_not(page):
    """Option A is our own counters; Cloudflare's edge metrics are option B and need a token.

    The panel claims the source in both languages, and explicitly does not claim Cloudflare's view
    of the network — which is what "网络活动" invites a reader to assume.
    """
    code = trend_code(page)
    assert 'data-i18n="' in code and "'activityTrendNote'" in code and "'activityTrendBounds'" in code, (
        "the note no longer carries a locale key for either provenance")
    for lang in ("en", "zh"):
        strings = locale(lang)
        for key in ("activityTrendTitle", "activityTrendNote", "activityTrendPartial",
                    "activityTrendBounds"):
            assert key in strings, f"{lang}.json has no {key}"
        assert "{days}" in strings["activityTrendTitle"], f"{lang}.json activityTrendTitle lost its placeholder"
        note = strings["activityTrendNote"]
        bounds = strings["activityTrendBounds"]
        if lang == "en":
            assert "Cloudflare" in note and "not" in note.lower(), note
            assert "lower bound" in bounds and "Cloudflare" in bounds, bounds
        else:
            assert "Cloudflare" in note and "非" in note, note
            assert "下界" in bounds and "Cloudflare" in bounds, bounds


def test_a_snapshot_derived_series_says_its_days_are_lower_bounds(page):
    """The bootstrap's numbers are "the day's count at the last snapshot", not the day's total.

    Drawing them as day totals would understate every day by the same unknown tail and let a reader
    compare them as if they were the endpoint's numbers. The chart wears the note the source asks for.
    """
    code = trend_code(page)
    assert "git-history:" in code, "the chart can no longer tell a snapshot-derived series apart"
    assert "activityTrendBounds" in code, "the lower-bound note is not rendered for it"


def test_the_headline_note_still_states_aggregate_and_no_identity():
    """The promise the section made before this change, kept while the source is named."""
    note = {"en": locale("en")["activityNote"], "zh": locale("zh")["activityNote"]}
    assert "aggregate" in note["en"] and "no identity" in note["en"], note
    assert "聚合" in note["zh"] and "不含身份" in note["zh"], note
    for lang, text in note.items():
        assert "Cloudflare" in text, f"{lang}.json activityNote no longer says what these numbers are not"


# ── it cannot take the panel down with it ─────────────────────────────────────────────────────────

def test_the_trend_is_loaded_after_the_numbers_and_is_not_the_numbers(page):
    """A slow or missing series must leave the headline standing; the containers are separate."""
    code = uncommented(page)
    loader = code[code.index("async function loadActivity()"):code.index("async function loadLatestUpdates()")]
    assert "loadActivityHistory()" in loader, "the trend is no longer triggered from the headline"
    assert 'id="activity-history"' in code, "the trend has no container of its own to fail in"
    assert "if (!slot) return;" in code, "a missing container would throw into the headline's render"


def test_the_trend_fetch_is_bounded(page):
    """Same bound as the headline's live read: a cold answer must not hold the card open."""
    code = trend_code(page)
    assert "ACTIVITY_LIVE_TIMEOUT_MS" in code, "the trend fetch is unbounded"
    match = re.search(r"const ACTIVITY_LIVE_TIMEOUT_MS = (\d+)", uncommented(page))
    assert match and 0 < int(match.group(1)) <= 8000, match and match.group(1)


def test_the_page_carries_no_per_day_fetch_loop(page):
    """The chart is one request, not one per bar — the shape that produced ~2,700 504s (#2151)."""
    code = trend_code(page)
    assert "series.map" in code, "the bars are no longer rendered from one payload"
    assert not re.search(r"for\s*\(.*series[\s\S]{0,200}fetch", code), "a fetch inside the series loop"
    assert "Promise.all" not in code, "the trend fans out per day"
