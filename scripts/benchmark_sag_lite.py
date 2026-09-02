#!/usr/bin/env python3
"""SAG-Lite performance benchmark — Issue #909.

Measures build time, per-query latency, throughput and top-1 accuracy of the
SAG-Lite FTS index, and compares it against the lessons.json keyword fallback
used by the MCP server. Results are written as JSON for reproducible baselines.

Usage:
    python3 scripts/benchmark_sag_lite.py
    python3 scripts/benchmark_sag_lite.py --json
    python3 scripts/benchmark_sag_lite.py --queries 25 --top 5
"""

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scripts.build_sag_index import build_index, search as sag_search

DEFAULT_OKF = REPO / "data" / "okf"
DEFAULT_DB = REPO / "data" / "sag-bench.db"
DEFAULT_QUERIES = 20
DEFAULT_TOP = 5

# Queries drawn from real lesson topics so accuracy is meaningful.
BENCH_QUERIES = [
    "MCP server",
    "playwright",
    "release notes",
    "Docker",
    "GPU",
    "WSL",
    "error handling",
    "web scraping",
    "security",
    "automation",
    "CI pipeline",
    "knowledge base",
    "lesson quality",
    "Linux",
    "Python",
    "cache",
    "search index",
    "cloudflare",
    "frontend",
    "API endpoint",
]


def measure_latency(search_fn, queries, top):
    """Run each query once, returning per-query latencies (ms)."""
    latencies = []
    for q in queries:
        start = time.perf_counter()
        search_fn(q, top=top)
        latencies.append((time.perf_counter() - start) * 1000.0)
    return latencies


def fallback_search(lessons, query, top=5):
    """Keyword fallback mirroring mcp_server._fallback_search scoring.

    Scores each lesson by the number of query terms found across title,
    summary, domain and tags; returns the top-N by score.
    """
    terms = [t.lower() for t in query.split() if t.strip()]
    scored = []
    for lesson in lessons:
        blob = " ".join(
            str(lesson.get(k, "")) for k in ("title", "summary", "domain", "tags")
        ).lower()
        score = sum(1 for t in terms if t in blob)
        if score > 0:
            scored.append((score, lesson))
    scored.sort(key=lambda pair: (-pair[0], str(pair[1].get("id", ""))))
    return [lesson for _, lesson in scored[:top]]


def load_lessons_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def run_benchmark(okf_path, db_path, queries, top, keep_db):
    """Run the full benchmark and return the results dict."""
    okf_path = Path(okf_path)
    db_path = Path(db_path)

    # 1. Build the SAG-Lite index (timed)
    build_start = time.perf_counter()
    build_index(okf_path, db_path)
    build_secs = time.perf_counter() - build_start

    # 2. SAG-Lite latency
    sag_lat = measure_latency(
        lambda q, top=top: sag_search(db_path, q, top=top), queries, top
    )

    # 3. Fallback latency + accuracy comparison
    lessons = load_lessons_json(REPO / "data" / "lessons.json")
    fb_lat = measure_latency(
        lambda q, top=top: fallback_search(lessons, q, top=top), queries, top
    )

    # 4. Accuracy: does SAG top-1 equal fallback top-1 for each query?
    # SAG returns `path` (e.g. lessons/contrib/x.md); the fallback returns
    # the lessons.json record with a `url`. Normalize both to the lesson
    # slug (basename without extension) before comparing.
    def lesson_slug(value: str | None) -> str | None:
        if not value:
            return None
        return Path(str(value).rstrip("/")).stem

    top1_match = 0
    for q in queries:
        sag_top = sag_search(db_path, q, top=1)
        fb_top = fallback_search(lessons, q, top=1)
        sag_id = lesson_slug(sag_top[0]["path"]) if sag_top else None
        fb_id = lesson_slug(fb_top[0].get("url") or fb_top[0].get("path")) if fb_top else None
        if sag_id and sag_id == fb_id:
            top1_match += 1

    results = {
        "queries": len(queries),
        "top": top,
        "build_secs": round(build_secs, 3),
        "sag_latency_ms": {
            "mean": round(sum(sag_lat) / len(sag_lat), 3),
            "min": round(min(sag_lat), 3),
            "max": round(max(sag_lat), 3),
        },
        "fallback_latency_ms": {
            "mean": round(sum(fb_lat) / len(fb_lat), 3),
            "min": round(min(fb_lat), 3),
            "max": round(max(fb_lat), 3),
        },
        "sag_throughput_qps": round(len(queries) / (sum(sag_lat) / 1000.0), 2),
        "top1_agreement_with_fallback": f"{top1_match}/{len(queries)}",
    }

    if not keep_db and db_path.exists():
        db_path.unlink()

    return results


def main():
    parser = argparse.ArgumentParser(description="SAG-Lite performance benchmark (#909)")
    parser.add_argument("--okf", default=str(DEFAULT_OKF), help="OKF lessons.jsonl path")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite output path")
    parser.add_argument("--queries", type=int, default=DEFAULT_QUERIES, help="number of queries")
    parser.add_argument("--top", type=int, default=DEFAULT_TOP, help="results per query")
    parser.add_argument("--json", action="store_true", help="output raw JSON")
    parser.add_argument("--keep-db", action="store_true", help="keep the built index after run")
    args = parser.parse_args()

    queries = BENCH_QUERIES[: args.queries]
    results = run_benchmark(args.okf, args.db, queries, args.top, args.keep_db)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print(f"SAG-Lite benchmark ({results['queries']} queries, top {results['top']}):")
        print(f"  build:            {results['build_secs']}s")
        print(f"  SAG latency:      {results['sag_latency_ms']['mean']}ms mean "
              f"({results['sag_latency_ms']['min']}-{results['sag_latency_ms']['max']})")
        print(f"  fallback latency: {results['fallback_latency_ms']['mean']}ms mean "
              f"({results['fallback_latency_ms']['min']}-{results['fallback_latency_ms']['max']})")
        print(f"  SAG throughput:   {results['sag_throughput_qps']} qps")
        print(f"  top-1 agreement:  {results['top1_agreement_with_fallback']}")


if __name__ == "__main__":
    main()
