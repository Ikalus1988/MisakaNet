#!/usr/bin/env python3
"""Tests for search gap logger and clustering.

Usage:
    python3 tests/test_search_gaps.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name}{': ' + detail if detail else ''}")


def test_log_zero_result():
    print("\n-- log_zero_result --")
    from scripts.search_gap_logger import log_zero_result

    # Use temp file to avoid polluting data/
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        tmp_path = f.name

    try:
        import scripts.search_gap_logger as gl
        original = gl.GAPS_FILE
        gl.GAPS_FILE = Path(tmp_path)

        # Valid query
        result = log_zero_result("pip install timeout proxy", source="mcp")
        check("logs valid query", result is True)

        # Empty query
        result = log_zero_result("", source="mcp")
        check("rejects empty query", result is False)

        # Whitespace-only
        result = log_zero_result("   ", source="mcp")
        check("rejects whitespace query", result is False)

        # Very long query
        result = log_zero_result("x" * 600, source="mcp")
        check("rejects too-long query", result is False)

        # Verify file content
        entries = []
        for line in Path(tmp_path).read_text().splitlines():
            if line.strip():
                entries.append(json.loads(line))
        check("wrote 1 entry", len(entries) == 1)
        check("entry has query", entries[0]["query"] == "pip install timeout proxy")
        check("entry has timestamp", "timestamp" in entries[0])
        check("entry has source", entries[0]["source"] == "mcp")

        gl.GAPS_FILE = original
    finally:
        os.unlink(tmp_path)


def test_normalize_query():
    print("\n-- normalize_query --")
    from scripts.search_gap_logger import normalize_query

    check("lowercase", normalize_query("PIP Install") == "pip install")
    check("strip punctuation", normalize_query("pip-install!timeout?") == "pip install timeout")
    check("collapse whitespace", normalize_query("pip   install  timeout") == "pip install timeout")


def test_cluster_queries():
    print("\n-- cluster_queries --")
    from scripts.gap_cluster import cluster_queries

    queries = [
        "pip install timeout",
        "pip install timeout proxy",
        "npm build error",
        "npm build failed",
        "docker compose up timeout",
        "pip install timeout corporate",
    ]

    clusters = cluster_queries(queries, threshold=0.4)
    check("produces clusters", len(clusters) > 0)
    check("first cluster has count", clusters[0]["count"] >= 2)
    check("clusters sorted by count", clusters[0]["count"] >= clusters[-1]["count"])

    # High threshold = fewer merges
    strict = cluster_queries(queries, threshold=0.9)
    check("high threshold = more clusters", len(strict) >= len(clusters))


def test_cluster_empty():
    print("\n-- cluster_queries empty --")
    from scripts.gap_cluster import cluster_queries

    clusters = cluster_queries([], threshold=0.5)
    check("empty input = empty output", clusters == [])

    clusters = cluster_queries([""], threshold=0.5)
    check("blank input = empty output", clusters == [])


def test_gap_stats():
    print("\n-- get_gap_stats --")
    from scripts.search_gap_logger import get_gap_stats, log_zero_result

    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        tmp_path = f.name

    try:
        import scripts.search_gap_logger as gl
        original = gl.GAPS_FILE
        gl.GAPS_FILE = Path(tmp_path)

        # Empty file
        stats = get_gap_stats()
        check("empty file stats", stats["total"] == 0)

        # Add some entries
        log_zero_result("query a", source="mcp")
        log_zero_result("query b", source="web")
        log_zero_result("query a", source="mcp")  # duplicate

        stats = get_gap_stats()
        check("stats total", stats["total"] == 3)
        check("stats unique", stats["unique_queries"] == 2)
        check("stats sources mcp", stats["sources"].get("mcp", 0) == 2)
        check("stats sources web", stats["sources"].get("web", 0) == 1)

        gl.GAPS_FILE = original
    finally:
        os.unlink(tmp_path)


if __name__ == "__main__":
    print("Search gap logger + clustering tests")
    test_log_zero_result()
    test_normalize_query()
    test_cluster_queries()
    test_cluster_empty()
    test_gap_stats()

    print(f"\n{'=' * 40}")
    print(f"Results: {PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)
