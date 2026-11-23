"""`scripts/install_baseline.py`: the baseline is the only reading of installs that means anything.

Why the arithmetic is tested separately from the network
-------------------------------------------------------
The finding this file protects (2026-11-23) is a *classification*, not a number: the day after a
publish is not a demand day. If the classifier drifts, the script keeps printing a confident average
of the wrong days — which is exactly the failure the script was written to end.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import install_baseline as ib  # noqa: E402


def test_a_publish_day_and_the_day_after_are_not_baseline():
    days = {"2026-11-12": 1031, "2026-11-13": 1047, "2026-11-14": 565, "2026-11-15": 416}
    labels = ib.classify(days, {"2026-11-13"})
    assert labels["2026-11-13"] == "release"
    assert labels["2026-11-14"] == "after", "the day after a publish is the re-resolution tail"
    assert labels["2026-11-15"] == "baseline"
    assert labels["2026-11-12"] == "baseline"


def test_the_average_uses_baseline_days_only():
    days = {"2026-11-10": 1000, "2026-11-11": 500, "2026-11-12": 200, "2026-11-13": 300,
            "2026-11-14": 400}
    labels = ib.classify(days, {"2026-11-10"})
    average, n = ib.window_average(days, labels, "2026-11-10", "2026-11-14")
    # 11-10 is release, 11-11 is the day after; 200, 300, 400 are the baseline.
    assert n == 3
    assert average == 300


def test_a_release_heavy_window_has_no_baseline_to_read():
    # A publish every single day: every day is either a release or the day after one.
    days = {f"2026-11-{d:02d}": 500 for d in range(9, 16)}
    publishes = {f"2026-11-{d:02d}" for d in range(9, 16)}
    labels = ib.classify(days, publishes)
    average, n = ib.window_average(days, labels, "2026-11-09", "2026-11-15")
    assert average is None and n == 0
    state, reason = ib.verdict(
        {"current": {"average": 150.0, "baseline_days": 4},
         "previous": {"average": None, "baseline_days": 0},
         "drop_percent": None}, 40)
    assert state == "cannot-judge"
    assert "baseline" in reason


def test_a_drop_at_the_threshold_is_a_drop():
    result = {"current": {"average": 120.0, "baseline_days": 5},
              "previous": {"average": 200.0, "baseline_days": 5},
              "drop_percent": ib.drop_percent(200.0, 120.0)}
    assert ib.verdict(result, 40)[0] == "dropped"
    assert ib.verdict(result, 41)[0] == "ok", "just under the threshold is not a drop"


def test_a_rise_is_never_a_drop():
    result = {"current": {"average": 300.0, "baseline_days": 5},
              "previous": {"average": 200.0, "baseline_days": 5},
              "drop_percent": ib.drop_percent(200.0, 300.0)}
    state, reason = ib.verdict(result, 40)
    assert state == "ok" and "+" in reason


def test_the_two_windows_do_not_overlap_and_end_where_asked():
    days = {f"2026-11-{d:02d}": 200 for d in range(1, 23)}
    result = ib.read_days(days, set(), window=7, end="2026-11-22")
    assert result["current"]["start"] == "2026-11-16"
    assert result["current"]["end"] == "2026-11-22"
    assert result["previous"]["start"] == "2026-11-09"
    assert result["previous"]["end"] == "2026-11-15"
    assert result["current"]["average"] == 200
    assert result["drop_percent"] == 0


def test_cannot_read_is_not_the_same_answer_as_fine():
    """The exit codes say so: 2 is "could not read", 0 is "read, nothing wrong"."""
    source = (REPO / "scripts" / "install_baseline.py").read_text(encoding="utf-8")
    assert "return 2" in source, "a registry failure must not exit 0"
    assert "cannot read" in source


def test_the_docstring_keeps_the_measurement_that_justifies_the_file():
    """The 2.2x number is the whole argument; if the file loses it, the next reader deletes the code."""
    doc = ib.__doc__ or ""
    assert "2.2x" in doc
    assert "472" in doc and "213" in doc
