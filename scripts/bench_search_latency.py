#!/usr/bin/env python3
"""Search Latency Benchmark — Issue #1050.

Measures p50/p95/p99 latency for each search engine:
  - SAG-Lite (FTS index)
  - Fallback (lessons.json keyword match)

Usage:
    python3 scripts/bench_search_latency.py              # full benchmark
    python3 scripts/bench_search_latency.py --queries 50 # custom query count
    python3 scripts/bench_search_latency.py --json       # JSON output only
"""

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA_DIR = REPO / "data"
sys.path.insert(0, str(REPO))

BENCH_QUERIES = [
    "MCP server setup", "playwright automation", "Docker compose",
    "GPU memory", "WSL filesystem", "Python virtualenv",
    "CI pipeline", "GitHub Actions", "error handling",
    "API rate limit", "web scraping", "security audit",
    "chroma rebuild", "embedding batch", "rag build",
    "feishu bot", "lesson quality", "search index",
    "knowledge base", "Docker network", "Redis cache",
    "Nginx config", "SSH tunnel", "SQLite performance",
    "a", "x", "test", "fix", "update",
    "Chinese encoding", "pymupdf4llm", "wsl2 memory leak",
    "fanuc robot", "PLC connection", "Karel program",
    "how to fix WSL2 memory leak",
    "MCP server authentication setup",
    "Docker container won't start",
    "Python import error no module named",
    "GitHub Actions workflow syntax error",
]


def percentile(data, p):
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * (p / 100)
    f = int(k)
    c = f + 1
    if c >= len(sorted_data):
        return sorted_data[-1]
    return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])


def load_engines():
    engines = {}
    try:
        from scripts.build_sag_index import search as sag_search, DEFAULT_DB
        engines["sag-lite"] = lambda q, top=5: sag_search(DEFAULT_DB, q, top=top)
    except (ImportError, FileNotFoundError, AttributeError):
        pass

    lessons_json = DATA_DIR / "lessons.json"
    if lessons_json.exists():
        lessons_data = json.loads(lessons_json.read_text())
        lessons_list = lessons_data if isinstance(lessons_data, list) else list(lessons_data.values())

        def fallback_search(query, top=5):
            query_lower = query.lower()
            scored = []
            for lesson in lessons_list:
                text = f"{lesson.get('title', '')} {' '.join(lesson.get('tags', []))}".lower()
                score = sum(1 for word in query_lower.split() if word in text)
                if score > 0:
                    scored.append((score, lesson.get('id', ''), lesson))
            scored.sort(key=lambda x: -x[0])
            return scored[:top]

        engines["fallback"] = fallback_search
    return engines


def bench_engine(name, search_fn, queries, top=5, warmup=3):
    for q in queries[:warmup]:
        try:
            search_fn(q, top=top)
        except Exception:
            pass

    latencies = []
    errors = 0
    for q in queries:
        start = time.perf_counter()
        try:
            search_fn(q, top=top)
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
        except Exception:
            errors += 1

    if not latencies:
        return {"engine": name, "queries": len(queries), "errors": errors,
                "p50_ms": 0, "p95_ms": 0, "p99_ms": 0,
                "mean_ms": 0, "min_ms": 0, "max_ms": 0, "total_ms": 0}

    return {
        "engine": name, "queries": len(queries), "errors": errors,
        "p50_ms": round(percentile(latencies, 50), 2),
        "p95_ms": round(percentile(latencies, 95), 2),
        "p99_ms": round(percentile(latencies, 99), 2),
        "mean_ms": round(statistics.mean(latencies), 2),
        "min_ms": round(min(latencies), 2),
        "max_ms": round(max(latencies), 2),
        "total_ms": round(sum(latencies), 2),
    }


def main():
    parser = argparse.ArgumentParser(description="Search latency benchmark")
    parser.add_argument("--queries", type=int, default=len(BENCH_QUERIES))
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", type=str)
    args = parser.parse_args()

    queries = BENCH_QUERIES[:args.queries]
    engines = load_engines()
    if not engines:
        print("No search engines available.", file=sys.stderr)
        sys.exit(1)

    print(f"Running benchmark: {len(queries)} queries x {len(engines)} engines")
    results = []
    for name, fn in engines.items():
        print(f"Benchmarking {name}...", end=" ", flush=True)
        r = bench_engine(name, fn, queries, args.top, args.warmup)
        results.append(r)
        print(f"p50={r['p50_ms']:.1f}ms p95={r['p95_ms']:.1f}ms")

    report = {
        "meta": {"queries": len(queries), "top": args.top, "warmup": args.warmup,
                 "engines": len(results), "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
        "results": results, "queries_used": queries,
    }

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"\n{'Engine':<12} {'p50':>8} {'p95':>8} {'p99':>8} {'mean':>8} {'errors':>7}")
        print("-" * 55)
        for r in results:
            print(f"{r['engine']:<12} {r['p50_ms']:>7.1f}ms {r['p95_ms']:>7.1f}ms "
                  f"{r['p99_ms']:>7.1f}ms {r['mean_ms']:>7.1f}ms {r['errors']:>6}")

    output = Path(args.output) if args.output else DATA_DIR / "search-latency.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    if not args.json:
        print(f"\nResults written to {output.relative_to(REPO)}")


if __name__ == "__main__":
    main()
