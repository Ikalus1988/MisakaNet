#!/usr/bin/env python3
"""Search Latency Benchmark — Issue #1050, and the only reproducible read of #4052.

Two things are measured here, and they are not the same thing:

  * **in-process** (`--engine`, the default): SAG-Lite (FTS index) and the naive fallback over
    `lessons.json`. These numbers are about the *code*, not about the service, and they are why
    this file could not answer #4052 — the hosted endpoint was taking 35–62 s while the local
    engines never moved.
  * **remote** (`--remote`): one `tools/call` to a running Misakanet endpoint per query, i.e. what
    a client actually waits for. It reports the **first call separately** (cold isolate: quota D1
    read, lesson load, index load) from the warm ones, because #4052's distribution was bimodal and
    an average over both modes is the number that hid it.

Usage:
    python3 scripts/bench_search_latency.py                     # local engines
    python3 scripts/bench_search_latency.py --queries 50        # custom query count
    python3 scripts/bench_search_latency.py --remote            # 20 hosted searches
    python3 scripts/bench_search_latency.py --remote --queries 6 --json
    python3 scripts/bench_search_latency.py --json              # JSON output only

Exit code: 0 when the measurement ran (whatever the numbers say), 1 when no engine or endpoint
answered at all. A slow run is a result, not a failure — the failure is a benchmark that reports
nothing and exits 0.
"""

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
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
        from scripts.build_sag_index import DEFAULT_DB
        from scripts.build_sag_index import search as sag_search
        engines["sag-lite"] = lambda q, top=5: sag_search(DEFAULT_DB, q, top=top)
    except (ImportError, FileNotFoundError, AttributeError):
        pass

    lessons_json = DATA_DIR / "lessons.json"
    if lessons_json.exists():
        lessons_data = json.loads(lessons_json.read_text(encoding="utf-8"))
        lessons_list = (lessons_data if isinstance(lessons_data, list)
                        else list(lessons_data.values()))

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


# ── remote mode (#4052) ─────────────────────────────────────────────────────────────────────────

DEFAULT_MCP_URL = "https://misakanet.org/mcp"

# The same headers every client sends, and the two the endpoint rejects a wrong value for. A probe
# that skipped `Origin` would be measuring a different server than the one agents talk to.
_MCP_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "MCP-Protocol-Version": "2025-06-18",
    "Origin": "https://misakanet.org",
    "User-Agent": "misakanet-bench-search-latency/1",
}


def _mcp_call(url: str, payload: dict, timeout: float) -> tuple[float, dict | None, str]:
    """One JSON-RPC request. Returns `(seconds, parsed body or None, error or "")`.

    The seam tests replace — the benchmark's arithmetic is what needs pinning, not urllib.
    """
    request = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"), headers=_MCP_HEADERS, method="POST")
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read()
            return time.perf_counter() - started, json.loads(body), ""
    except Exception as exc:  # HTTPError, URLError, timeout, a non-JSON body
        return time.perf_counter() - started, None, f"{type(exc).__name__}: {exc}"


def _search_payload(query: str, top: int = 2) -> dict:
    return {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "misakanet_search", "arguments": {"query": query, "top": top}}}


def _source_of(body: dict | None) -> str:
    """The `source` the endpoint reports (`worker-bm25` / `semantic`), when there is one."""
    if not isinstance(body, dict):
        return ""
    result = body.get("result") or {}
    structured = result.get("structuredContent") or {}
    if structured.get("source"):
        return str(structured["source"])
    content = (result.get("content") or [{}])
    text = content[0].get("text", "") if content and isinstance(content[0], dict) else ""
    try:
        return str(json.loads(text).get("source") or "")
    except Exception:
        return ""


def bench_remote(queries, url: str = DEFAULT_MCP_URL, timeout: float = 90.0,
                 call=_mcp_call) -> dict:
    """Measure what a client waits for, cold call included and reported separately.

    The first call is kept out of the percentiles on purpose: on a cold isolate it pays the
    index load, and mixing it into p50 is how a bimodal distribution becomes one comfortable
    number. It is reported as `cold_ms` instead, and named in the text output.
    """
    rows, errors, sources = [], 0, {}
    cold_ms = None
    for index, query in enumerate(queries):
        seconds, body, error = call(url, _search_payload(query), timeout)
        if error:
            errors += 1
            continue
        source = _source_of(body)
        if source:
            sources[source] = sources.get(source, 0) + 1
        if index == 0:
            cold_ms = round(seconds * 1000, 2)
            continue
        rows.append(seconds * 1000)

    if not rows:
        return {"engine": "remote-worker", "queries": len(queries), "errors": errors,
                "url": url, "cold_ms": cold_ms, "sources": sources,
                "p50_ms": 0, "p95_ms": 0, "p99_ms": 0,
                "mean_ms": 0, "min_ms": 0, "max_ms": 0}
    return {
        "engine": "remote-worker", "queries": len(queries), "errors": errors,
        "url": url, "cold_ms": cold_ms, "sources": sources,
        "warm_samples": len(rows),
        "p50_ms": round(percentile(rows, 50), 2),
        "p95_ms": round(percentile(rows, 95), 2),
        "p99_ms": round(percentile(rows, 99), 2),
        "mean_ms": round(statistics.mean(rows), 2),
        "min_ms": round(min(rows), 2),
        "max_ms": round(max(rows), 2),
    }


def _remote_lines(result: dict) -> list[str]:
    cold = "n/a" if result["cold_ms"] is None else f"{result['cold_ms'] / 1000:.2f}s"
    lines = [
        f"engine          : remote-worker ({result['url']})",
        f"samples         : {result.get('warm_samples', 0)} warm / {result['queries']} sent "
        f"({result['errors']} error(s))",
        f"cold (first)    : {cold}",
    ]
    if result.get("warm_samples"):
        lines.append(f"warm p50/p95    : {result['p50_ms'] / 1000:.2f}s / "
                     f"{result['p95_ms'] / 1000:.2f}s")
        lines.append(f"warm max        : {result['max_ms'] / 1000:.2f}s")
    if result.get("sources"):
        lines.append("sources         : "
                     + ", ".join(f"{k}={v}" for k, v in sorted(result["sources"].items())))
    if result.get("max_ms", 0) >= 30000:
        lines.append("warn            : at least one call took ≥30s — that is the #4052 shape, and "
                     "a client with a normal timeout reads it as `fetch failed`")
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(description="Search latency benchmark")
    parser.add_argument("--queries", type=int, default=None,
                        help="how many queries (local: all; remote: 20)")
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", type=str)
    parser.add_argument("--remote", action="store_true",
                        help="measure a running endpoint instead of this checkout's engines")
    parser.add_argument("--url", type=str, default=DEFAULT_MCP_URL,
                        help=f"endpoint for --remote (default {DEFAULT_MCP_URL})")
    parser.add_argument("--timeout", type=float, default=90.0,
                        help="per-request timeout for --remote, in seconds (default 90)")
    args = parser.parse_args(argv)

    default_count = 20 if args.remote else len(BENCH_QUERIES)
    count = args.queries if args.queries is not None else default_count
    if args.remote:
        queries = _cycled(BENCH_QUERIES, max(1, count))
        result = bench_remote(queries, args.url, args.timeout)
        report = {
            "meta": {"mode": "remote", "queries": len(queries), "top": 2,
                     "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
            "results": [result], "queries_used": queries,
        }
        if args.json:
            print(json.dumps(report, indent=2))
            return 0
        print(f"Remote benchmark: {len(queries)} queries -> {args.url}")
        print("\n".join(_remote_lines(result)))
        if args.output:
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"\nResults written to {output}")
        # A slow run is the result; only "nothing answered" is a failure.
        return 1 if result["errors"] == len(queries) else 0

    queries = _cycled(BENCH_QUERIES, max(1, count))
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
                 "engines": len(results),
                 "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
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
    return 0


def _cycled(queries: list[str], count: int) -> list[str]:
    """`count` queries, repeating the list when the caller asks for more than it holds."""
    return [queries[i % len(queries)] for i in range(count)]


if __name__ == "__main__":
    raise SystemExit(main())
