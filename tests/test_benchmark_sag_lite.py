#!/usr/bin/env python3
"""Tests for the SAG-Lite benchmark script (Issue #909).

The benchmark runs a real SQLite build + queries, so tests use a tiny
synthetic OKF corpus and a temp DB to keep them fast and hermetic.
"""
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

import pytest

from scripts.benchmark_sag_lite import (
    BENCH_QUERIES,
    fallback_search,
    load_lessons_json,
    measure_latency,
    run_benchmark,
)


@pytest.fixture
def tiny_okf(tmp_path):
    """A tiny OKF lessons.jsonl with two lessons."""
    lines = [
        json.dumps({"id": "mcp", "title": "MCP server guide", "domain": "core",
                    "tags": ["mcp"], "summary": "Build an MCP server", "path": "lessons/core/mcp.md"}),
        json.dumps({"id": "gpu", "title": "GPU setup", "domain": "core",
                    "tags": ["gpu"], "summary": "Configure GPU drivers", "path": "lessons/core/gpu.md"}),
    ]
    d = tmp_path / "okf"
    d.mkdir()
    (d / "lessons.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return d


@pytest.fixture
def tiny_lessons_json(tmp_path):
    """lessons.json mirroring the fixture lessons (for fallback)."""
    lessons = [
        {"id": "mcp", "title": "MCP server guide", "domain": "core",
         "tags": ["mcp"], "summary": "Build an MCP server", "path": "lessons/core/mcp.md"},
        {"id": "gpu", "title": "GPU setup", "domain": "core",
         "tags": ["gpu"], "summary": "Configure GPU drivers", "path": "lessons/core/gpu.md"},
    ]
    p = tmp_path / "lessons.json"
    p.write_text(json.dumps(lessons), encoding="utf-8")
    return p


class TestFallbackSearch:
    def test_matches_by_term(self, tiny_lessons_json):
        lessons = json.loads(tiny_lessons_json.read_text())
        results = fallback_search(lessons, "MCP server", top=5)
        assert results
        assert results[0]["id"] == "mcp"

    def test_top_limit_respected(self, tiny_lessons_json):
        lessons = json.loads(tiny_lessons_json.read_text())
        assert len(fallback_search(lessons, "core", top=1)) <= 1

    def test_no_match_returns_empty(self, tiny_lessons_json):
        lessons = json.loads(tiny_lessons_json.read_text())
        assert fallback_search(lessons, "zzzznope", top=5) == []


class TestMeasureLatency:
    def test_returns_one_entry_per_query(self):
        calls = []
        lat = measure_latency(lambda q, top=5: calls.append(q), ["a", "b"], 5)
        assert len(lat) == 2
        assert all(isinstance(x, float) for x in lat)

    def test_zero_cost_fn_still_returns_numbers(self):
        lat = measure_latency(lambda q, top=5: None, ["a", "b", "c"], 5)
        assert len(lat) == 3
        assert all(x >= 0 for x in lat)


class TestRunBenchmark:
    def test_full_benchmark_produces_expected_shape(self, tmp_path, tiny_okf, tiny_lessons_json):
        # Point the fallback at the tiny lessons.json by monkeypatching REPO
        import scripts.benchmark_sag_lite as bench

        db = tmp_path / "sag-bench.db"
        # run_benchmark reads REPO/data/lessons.json — patch the module's REPO
        # so load_lessons_json uses our fixture dir.
        fake_repo = tmp_path
        (fake_repo / "data").mkdir(exist_ok=True)
        (fake_repo / "data" / "lessons.json").write_text(tiny_lessons_json.read_text(), encoding="utf-8")

        monkeypatch_repo = lambda: None
        bench.REPO = fake_repo

        results = run_benchmark(tiny_okf, db, ["MCP server", "GPU setup"], 5, keep_db=False)

        assert "build_secs" in results
        assert "sag_latency_ms" in results
        assert "fallback_latency_ms" in results
        assert "sag_throughput_qps" in results
        assert results["queries"] == 2
        assert results["sag_latency_ms"]["mean"] >= 0
        assert not db.exists(), "benchmark must clean up its temp DB by default"

    def test_queries_are_meaningful_topics(self):
        assert len(BENCH_QUERIES) >= 10
        assert all(isinstance(q, str) and q.strip() for q in BENCH_QUERIES)
