#!/usr/bin/env python3
"""The latency benchmark, tested where it decides something (#1050, #4052).

Two modes, two different questions:

  * the local engines answer "how fast is this checkout's search code";
  * `--remote` answers "what does a client actually wait for", which is the only question #4052
    asks — the hosted endpoint took 35–62 s while every local engine stayed in the tens of
    milliseconds. That mode did not exist, so the issue's own reproduction was the only
    measurement anyone had.

The arithmetic is pinned here with a fake `call`: the first call is reported as `cold_ms` and kept
out of the percentiles (a cold isolate pays an index load that no steady-state number should hide),
errors are counted rather than silently skipped, and a run where nothing answered exits 1 while a
run that is merely slow exits 0.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts import bench_search_latency as bench  # noqa: E402


def fake_call(*, seconds, source="worker-bm25", error=""):
    """A `call` stand-in. `seconds` is a list consumed in order (the last value repeats)."""
    remaining = list(seconds)

    def call(url, payload, timeout):
        delay = remaining.pop(0) if len(remaining) > 1 else remaining[0]
        if error:
            return delay, None, error
        body = {"result": {"structuredContent": {"source": source, "results": []}}}
        return delay, body, ""

    return call


def test_the_first_call_is_reported_as_cold_and_left_out_of_the_percentiles():
    """#4052's distribution was bimodal; averaging the cold call in is how that disappeared."""
    result = bench.bench_remote(["q1", "q2", "q3"], call=fake_call(seconds=[10.0, 2.0, 3.0]))
    assert result["cold_ms"] == 10000.0
    assert result["warm_samples"] == 2
    assert result["p50_ms"] >= 2000.0 and result["p50_ms"] <= 3000.0
    assert result["max_ms"] == 3000.0, "the cold call must not become the max"


def test_errors_are_counted_and_do_not_become_zero_latencies():
    def call(url, payload, timeout):
        return 0.5, None, "URLError: timed out"

    result = bench.bench_remote(["q1", "q2"], call=call)
    assert result["errors"] == 2
    assert result.get("warm_samples", 0) == 0
    assert result["p50_ms"] == 0, "no samples is reported as zero samples, not a fast zero"


def test_sources_are_counted_so_a_semantic_fallback_is_visible():
    result = bench.bench_remote(["q1", "q2", "q3"],
                                call=fake_call(seconds=[1.0, 1.0, 1.0], source="semantic"))
    assert result["sources"] == {"semantic": 3}


def test_the_source_is_read_from_the_content_text_when_there_is_no_structured_content():
    body = {"result": {"content": [{"type": "text",
                                    "text": json.dumps({"source": "worker-bm25+semantic"})}]}}
    assert bench._source_of(body) == "worker-bm25+semantic"


def test_the_text_output_names_the_slow_tail():
    """The whole point of the number: a client reads ≥30s as `fetch failed`, not as "slow"."""
    result = bench.bench_remote(["q1", "q2"], call=fake_call(seconds=[1.0, 45.0]))
    text = "\n".join(bench._remote_lines(result))
    assert "cold (first)" in text
    assert "warn" in text and "#4052" in text


def test_a_fast_run_says_nothing_about_the_slow_tail():
    result = bench.bench_remote(["q1", "q2"], call=fake_call(seconds=[1.0, 2.0]))
    assert "warn" not in "\n".join(bench._remote_lines(result))


def test_more_queries_than_the_list_holds_cycles_the_list():
    assert bench._cycled(["a", "b"], 5) == ["a", "b", "a", "b", "a"]


def test_remote_mode_exits_one_only_when_nothing_answered(monkeypatch, capsys):
    monkeypatch.setattr(bench, "bench_remote", lambda queries, url, timeout: {
        "engine": "remote-worker", "url": url, "queries": len(queries), "errors": len(queries),
        "cold_ms": None, "sources": {}, "p50_ms": 0, "p95_ms": 0, "p99_ms": 0,
        "mean_ms": 0, "min_ms": 0, "max_ms": 0,
    })
    assert bench.main(["--remote", "--queries", "2"]) == 1, (
        "a benchmark that measured nothing must not exit 0 — that is the failure "
        "`test_ci_runs_what_it_claims.py` exists to prevent elsewhere"
    )
    assert "0 warm / 2 sent" in capsys.readouterr().out


def test_a_slow_remote_run_still_exits_zero(monkeypatch, capsys):
    monkeypatch.setattr(bench, "bench_remote", lambda queries, url, timeout: {
        "engine": "remote-worker", "url": url, "queries": len(queries), "errors": 0,
        "cold_ms": 1000.0, "sources": {"worker-bm25": len(queries)}, "warm_samples": len(queries),
        "p50_ms": 50000.0, "p95_ms": 62000.0, "p99_ms": 62200.0,
        "mean_ms": 48000.0, "min_ms": 30000.0, "max_ms": 62220.0,
    })
    # A slow measurement is a result. Exiting non-zero here would make the probe unusable in CI —
    # the thing to fail on is "nothing answered", which the previous test pins.
    assert bench.main(["--remote", "--queries", "2"]) == 0
    assert "#4052" in capsys.readouterr().out
