#!/usr/bin/env python3
"""The first-byte check must fail on the regression it exists for, and refuse to fail on a bad network.

Two ways this kind of check goes wrong, both cheap to write and expensive to live with:

* it asserts absolute milliseconds from a CI runner, and goes red on a busy morning — nobody reads it
  after the second false alarm;
* it fails when the *measurement* failed, so "could not reach the host" is reported as "streaming
  regressed".

`verdict()` is a pure function of three summaries, which is why these tests need no network: the
judgement is testable in isolation from the thing it judges.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

spec = importlib.util.spec_from_file_location("bench_ttfb", REPO / "scripts" / "bench_ttfb.py")
bt = importlib.util.module_from_spec(spec)
# Registered before exec: `@dataclass` resolves the module by name through `sys.modules`, and a
# module that was never registered trips it with `AttributeError: 'NoneType' has no '__dict__'`.
sys.modules["bench_ttfb"] = bt
spec.loader.exec_module(bt)


def summary(*, ok=5, samples=5, first=200, total=2000, rate=None):
    return {"samples": samples, "ok": ok, "ok_rate": rate if rate is not None else ok / samples,
            "first_p50_ms": first, "first_min_ms": first, "first_max_ms": first,
            "total_p50_ms": total, "bytes_p50": 4000, "errors": []}


HEALTHY_BASELINE = summary(first=1200, total=1300)


def test_a_streamed_answer_passes():
    got = bt.verdict(HEALTHY_BASELINE, summary(first=3000, total=4000),
                     summary(first=800, total=4000))
    assert got["status"] == "pass", got
    assert all(c["ok"] for c in got["checks"]), got["checks"]


def test_a_buffered_answer_fails_the_assertion_it_exists_for():
    """The regression: first byte arrives at the same moment the last one does."""
    got = bt.verdict(HEALTHY_BASELINE, summary(first=3000, total=4000),
                     summary(first=3950, total=4000))
    assert got["status"] == "fail", got
    assert any("sse streams" in r for r in got["reasons"]), got["reasons"]


def test_a_slow_baseline_makes_the_whole_run_inconclusive():
    """A bad link must not be reported as a code regression, and 5 s is the line."""
    flaky = bt.verdict(summary(ok=1, samples=5, first=6000), summary(first=9000, total=9500),
                       summary(first=9000, total=9500))
    assert flaky["status"] == "inconclusive", flaky
    assert "network baseline" in flaky["reasons"][0]

    slow = bt.verdict(summary(first=6000), summary(first=6000, total=7000),
                      summary(first=6000, total=7000))
    assert slow["status"] == "inconclusive", slow


def test_streaming_must_not_be_slower_than_the_buffered_path():
    got = bt.verdict(HEALTHY_BASELINE, summary(first=1000, total=2000),
                     summary(first=3000, total=4000))
    assert got["status"] == "fail", got
    assert any("not slower" in r for r in got["reasons"]), got["reasons"]


def test_success_rates_catch_an_endpoint_that_is_down():
    got = bt.verdict(HEALTHY_BASELINE, summary(ok=0, samples=5, first=None, total=None),
                     summary(ok=0, samples=5, first=None, total=None))
    assert got["status"] == "fail", got
    assert any("sse answers" in r for r in got["reasons"]), got["reasons"]
    assert any("json answers" in r for r in got["reasons"]), got["reasons"]


def test_the_report_says_inconclusive_in_words_not_just_in_a_field():
    report = {"measured_at": "2026-10-31T00:00:00Z", "host": "example.test", "samples": 5,
              "series": {"baseline (tools/list)": summary(first=9000),
                         "search (json)": summary(first=9000, total=9500),
                         "search (sse)": summary(first=9000, total=9500)},
              "verdict": {"status": "inconclusive", "reasons": ["network baseline is unreliable"],
                          "checks": []}}
    text = bt.render(report)
    assert "inconclusive" in text
    assert "nothing here is a judgement on the code" in text
    assert "## Why it did not measure" in text


def test_the_report_table_carries_both_timings():
    report = {"measured_at": "2026-10-31T00:00:00Z", "host": "example.test", "samples": 5,
              "series": {"search (sse)": summary(first=800, total=4000)},
              "verdict": {"status": "pass", "reasons": [], "checks": []}}
    text = bt.render(report)
    assert "800 ms" in text and "4000 ms" in text
