#!/usr/bin/env python3
"""`scripts/bench_production_recall.py` — the parts that can be checked without the live service.

Why a test for a probe script
-----------------------------
The script exists to make one number visible: the gate in `workers/search-dual-floor.test.mjs` measures
the *repository* corpus (418 rows, `summary` + `preview`) while production serves a different one (426
rows, the D1 `rich` projection), and on 2026-09-28 the same 42 queries scored 13/20 · 18/20 and
11/22 · 14/22 live against floors of 16/19 and 11/15. A script that reports that comparison is only
worth having if its arithmetic and its floor reading are right — a probe that mis-tallies is worse than
no probe, because it produces a confident wrong number in exactly the situation someone is trying to
understand.

So the network is the one thing not tested here (it is not in CI — see the script's own header); the
floors, the tally, the comparison and the rendering are.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts import bench_production_recall as bench  # noqa: E402


def rows() -> list[dict]:
    return bench.load_rows()


# ── the floors come from the gate, not from a second copy ───────────────────────────────────────────

def test_the_floors_are_read_from_the_gate_that_enforces_them():
    floors = bench.load_floors()
    assert set(floors) == {"en", "zh"}, floors
    for language in ("en", "zh"):
        assert set(floors[language]) == {"hit1", "hit3"}, floors[language]
        assert all(isinstance(value, int) for value in floors[language].values()), floors[language]

    # Cross-read: the same numbers the schema test parses out of the same file. If the bench changes
    # shape, both readers must break together rather than one of them silently reading nothing.
    source = bench.BENCH.read_text(encoding="utf-8")
    independent = {name: (int(hit1), int(hit3))
                   for name, hit1, hit3 in re.findall(
                       r"export const (EN_FLOOR|ZH_FLOOR) = \{ hit1: (\d+), hit3: (\d+) \};", source)}
    assert independent["EN_FLOOR"] == (floors["en"]["hit1"], floors["en"]["hit3"]), independent
    assert independent["ZH_FLOOR"] == (floors["zh"]["hit1"], floors["zh"]["hit3"]), independent


def test_a_floor_above_the_number_of_queries_is_rejected_as_unreadable(tmp_path):
    """Guard: a floor that cannot be met is not a floor — and a missing declaration must not read as 0."""
    broken = tmp_path / "bench.mjs"
    broken.write_text("// the floors moved somewhere else\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        bench.load_floors(broken)


def test_every_floor_is_reachable_with_the_rows_that_exist():
    floors = bench.load_floors()
    for language in ("en", "zh"):
        total = sum(1 for row in rows() if row["language"] == language)
        assert floors[language]["hit1"] <= total, (language, floors[language], total)
        assert floors[language]["hit3"] <= total, (language, floors[language], total)
        assert floors[language]["hit1"] <= floors[language]["hit3"], (language, floors[language])


def test_the_script_is_not_wired_into_ci():
    """A script that needs the live service must not be a gate.

    Structural, not textual: it looks for the filename in the workflow files rather than for a
    sentence, because a comment saying "not in CI" is what a gate that *is* in CI also says.
    """
    workflows = sorted((REPO / ".github" / "workflows").glob("*.yml"))
    assert workflows, "no workflows found — the check would pass for the wrong reason"
    offenders = [path.name for path in workflows
                 if "bench_production_recall" in path.read_text(encoding="utf-8")]
    assert not offenders, f"a live-network probe must not run in CI: {offenders}"


# ── the arithmetic ─────────────────────────────────────────────────────────────────────────────────

FIXTURE_ROWS = [
    {"id": "a", "language": "en", "query": "first", "expected": ["hit"]},
    {"id": "b", "language": "en", "query": "second", "expected": ["hit"]},
    {"id": "c", "language": "en", "query": "third", "expected": ["hit"]},
    {"id": "d", "language": "en", "query": "fourth", "expected": ["hit"]},
    {"id": "e", "language": "zh", "query": "第五", "expected": ["hit"]},
]


def test_the_tally_counts_the_rank_window_it_was_given():
    results = {
        "a": {"ids": ["hit", "other"]},                      # rank 1 → hit1 and hit3
        "b": {"ids": ["other", "other2", "hit"]},            # rank 3 → hit3 only
        "c": {"ids": ["other", "other2", "other3", "hit"]},  # rank 4 → neither
        "d": {"ids": [], "no_match": True},                  # no answer
        "e": {"ids": ["hit"]},                               # zh, rank 1
    }
    tallies = bench.tally(FIXTURE_ROWS, results, top=3)
    assert (tallies["en"]["total"], tallies["en"]["hit1"], tallies["en"]["hit3"]) == (4, 1, 2), tallies["en"]
    assert (tallies["zh"]["total"], tallies["zh"]["hit1"], tallies["zh"]["hit3"]) == (1, 1, 1), tallies["zh"]
    missed = {miss["query"] for miss in tallies["en"]["misses"]}
    assert missed == {"third", "fourth"}, tallies["en"]["misses"]
    assert any(miss["no_match"] for miss in tallies["en"]["misses"] if miss["query"] == "fourth")

    # The window is a parameter, and widening it must change the answer — otherwise `--top` is a
    # decoration and the gate's own top-3 would be hard-coded without anyone noticing.
    wider = bench.tally(FIXTURE_ROWS, results, top=4)
    assert (wider["en"]["hit1"], wider["en"]["hit3"]) == (1, 3), wider["en"]


def test_a_transport_error_is_reported_and_not_silently_counted_as_a_miss():
    """The 403-on-every-row run of 2026-09-28 is why: it looked exactly like a recall collapse."""
    results = {"a": {"ids": ["hit"]}, "b": {"ids": [], "error": "HTTP 403"},
               "c": {"ids": [], "error": "HTTP 403"}, "d": {"ids": ["hit"]}, "e": {"ids": ["hit"]}}
    tallies = bench.tally(FIXTURE_ROWS, results, top=3)
    assert [error["error"] for error in tallies["en"]["errors"]] == ["HTTP 403", "HTTP 403"], tallies["en"]


def test_the_comparison_flags_a_below_floor_result_and_not_an_equal_one():
    floors = {"en": {"hit1": 2, "hit3": 3}, "zh": {"hit1": 1, "hit3": 1}}
    at_floor = {"en": {"total": 4, "hit1": 2, "hit3": 3}, "zh": {"total": 1, "hit1": 1, "hit3": 1}}
    comparison = bench.compare(at_floor, floors)
    assert comparison["en"]["below_floor"] is False, comparison["en"]
    assert (comparison["en"]["delta_hit1"], comparison["en"]["delta_hit3"]) == (0, 0), comparison["en"]

    below = {"en": {"total": 4, "hit1": 1, "hit3": 2}, "zh": {"total": 1, "hit1": 1, "hit3": 1}}
    comparison = bench.compare(below, floors)
    assert comparison["en"]["below_floor"] is True, comparison["en"]
    assert (comparison["en"]["delta_hit1"], comparison["en"]["delta_hit3"]) == (-1, -1), comparison["en"]
    assert comparison["zh"]["below_floor"] is False, comparison["zh"]


def test_a_language_with_no_rows_cannot_pass_the_comparison_by_absence():
    """A floor over an empty set is met trivially; the render has to make that visible."""
    floors = {"en": {"hit1": 2, "hit3": 3}, "zh": {"hit1": 1, "hit3": 1}}
    comparison = bench.compare({"en": {"total": 4, "hit1": 2, "hit3": 3}}, floors)
    assert comparison["zh"]["total"] == 0, comparison["zh"]
    assert comparison["zh"]["below_floor"] is True, (
        "zero rows must not read as 'at the floor': the gate's numbers are counts, not ratios")


# ── the report ─────────────────────────────────────────────────────────────────────────────────────

def test_the_report_prints_both_corpora_and_names_every_miss():
    # Floors above what the fixture provides, so the report's below-floor marker is exercised here
    # rather than in a second test that would assert the same line twice.
    floors = {"en": {"hit1": 2, "hit3": 2}, "zh": {"hit1": 1, "hit3": 1}}
    results = {"a": {"ids": ["hit"]}, "b": {"ids": ["other"]}, "c": {"ids": ["other"]},
               "d": {"ids": ["other"]}, "e": {"ids": ["hit"]}}
    tallies = bench.tally(FIXTURE_ROWS, results, top=3)
    # The repository-corpus number is **derived**, never written down. This test used to assert the
    # literal `418`, and on 2026-09-29 that made it block the daily sync PR (#2433), which legitimately
    # moves `data/lessons.json` to 426 — the same "a pinned value with no writer" shape the repository
    # keeps fixing elsewhere, this time in a test of mine. Deriving it asserts the property that matters
    # (the report prints the corpus it actually read) and cannot go stale.
    repo_rows = len(json.loads(bench.REPO_CORPUS.read_text(encoding="utf-8")))
    report = bench.render(bench.compare(tallies, floors), tallies,
                          {"docCount": 426, "textMode": "rich", "textVersion": 4,
                           "expectedTextVersion": 4, "textVersionCurrent": True,
                           "cjkChannel": {"termCount": 10519, "docCount": 426}},
                          repo_rows, floors, "2026-09-28, data/lessons.json at 418 rows")
    assert f"repository corpus: {repo_rows} rows" in report, report
    assert repo_rows > 0, "the corpus must exist for this assertion to mean anything"
    assert "426 rows, textMode rich" in report, report
    assert "10519 bigrams" in report, report
    assert "second" in report and "expected ['hit']" in report, report
    assert "below the floor" in report, report


def test_the_report_says_so_when_the_index_is_unreachable():
    floors = {"en": {"hit1": 0, "hit3": 0}, "zh": {"hit1": 0, "hit3": 0}}
    report = bench.render(bench.compare({"en": {"total": 0}, "zh": {"total": 0}}, floors),
                          {}, {"error": "URLError: timed out"}, 418, floors, "unknown")
    assert "index unavailable" in report, report
    assert "URLError" in report, report


def test_the_measured_on_line_is_read_from_the_gate():
    assert bench.measured_on().startswith("2026-"), bench.measured_on()
