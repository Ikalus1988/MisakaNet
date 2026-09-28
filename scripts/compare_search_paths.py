#!/usr/bin/env python3
"""Compare the worker's two search implementations over the same queries (issue #2121).

The worker answers a search question two ways, and the decision in #2121 is which one to keep:

* **KV BM25** — `buildBM25Index()` into `worker_search_index`, served by `misakanet_search` as
  `source: "worker-bm25"` (the path the #2091 ranking fix landed on);
* **D1 FTS5** — `lessons_fts MATCH` in the `/api/lessons?q=` path, served as `source: "d1-fts5"`,
  built by `sync_lessons_to_d1.py` on every sync.

Two implementations of one behaviour drift, and #2080 is what that costs: the D1 side carried the
derived `evidence_level` while the KV index did not, so "the fix is deployed" and "the user sees it"
became different statements.

This script produces the evidence the decision needs — recall@k and rank of the first expected lesson,
per path, over `data/regression_queries.json`, plus each path's latency. It reads only public
endpoints; nothing here writes, and it is not part of CI (it needs the live service).

Usage:
    python3 scripts/compare_search_paths.py                 # all queries
    python3 scripts/compare_search_paths.py --top 5 --json  # machine-readable
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
QUERIES = REPO / "data" / "regression_queries.json"
MCP_URL = "https://misakanet.org/mcp"
FTS_URL = "https://misakanet.org/api/lessons"
USER_AGENT = "misakanet-agent/1.0 (+https://misakanet.org; search-path comparison)"


def fetch(url: str, *, data: bytes | None = None, headers: dict | None = None,
          timeout: float = 20.0, attempts: int = 3) -> tuple[dict | list, float]:
    """GET/POST with retries, returning (payload, seconds).

    Retries are not decoration: the service intermittently stalls (issue #2126), so a single timeout
    would report a latency figure for a request that never happened. A query that fails every attempt
    is reported as a miss rather than silently dropped.
    """
    last: Exception | None = None
    for attempt in range(attempts):
        started = time.monotonic()
        try:
            req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT,
                                                                  **(headers or {})})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode() or "null")
            return payload, time.monotonic() - started
        except Exception as exc:  # noqa: BLE001 — a failed attempt is data
            last = exc
            time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"{url}: {last}")


def bm25_search(query: str, top: int) -> tuple[list[str], float]:
    body = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "misakanet_search",
                   "arguments": {"query": query, "top": top, "detail": "compact"}},
    }).encode()
    payload, seconds = fetch(MCP_URL, data=body, headers={
        "Content-Type": "application/json", "Accept": "application/json",
        "MCP-Protocol-Version": "2025-06-18", "Origin": "https://misakanet.org"})
    text = payload["result"]["content"][0]["text"]
    data = json.loads(text)
    ids = [str(r.get("id") or "") for r in data.get("results") or []]
    return ids, seconds


def fts_search(query: str, top: int) -> tuple[list[str], float]:
    from urllib.parse import quote
    payload, seconds = fetch(f"{FTS_URL}?q={quote(query)}&limit={top}")
    # The endpoint answers two shapes: a bare list for the unfiltered listing, and
    # `{query, results, source}` for the FTS path — reading only `lessons` made every FTS query look
    # like it returned nothing, which is the kind of wrong answer a comparison script must not invent.
    if isinstance(payload, list):
        rows = payload
    else:
        rows = payload.get("results") or payload.get("lessons") or []
    ids = [str(r.get("id") or "") for r in rows]
    return ids, seconds


def rank_of_expected(ids: list[str], expected: list[str]) -> int | None:
    """1-based rank of the first expected lesson, matching on the file stem (the two paths key
    differently: the MCP hit id is the stem, the FTS row carries both)."""
    wanted = {Path(p).stem for p in expected}
    for i, hit in enumerate(ids, 1):
        if hit in wanted or Path(hit).stem in wanted:
            return i
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    spec = json.loads(QUERIES.read_text(encoding="utf-8"))
    rows = []
    for entry in spec["queries"]:
        query = entry["query"]
        expected = entry.get("expected_lessons") or []
        row = {"id": entry.get("id"), "query": query, "expected": len(expected)}
        for name, fn in (("bm25", bm25_search), ("fts5", fts_search)):
            try:
                ids, seconds = fn(query, args.top)
                row[f"{name}_ids"] = ids
                row[f"{name}_rank"] = rank_of_expected(ids, expected)
                row[f"{name}_seconds"] = round(seconds, 3)
                row[f"{name}_n"] = len(ids)
            except Exception as exc:  # noqa: BLE001
                row[f"{name}_error"] = str(exc)[:120]
        rows.append(row)
        print(f"{row['id']:<10} bm25 rank={row.get('bm25_rank')} "
              f"({row.get('bm25_seconds')}s, n={row.get('bm25_n')}) | "
              f"fts5 rank={row.get('fts5_rank')} ({row.get('fts5_seconds')}s, n={row.get('fts5_n')})"
              f"  ← {query[:44]}")

    def summarise(name: str) -> dict:
        ranks = [r[f"{name}_rank"] for r in rows if r.get(f"{name}_rank")]
        lat = [r[f"{name}_seconds"] for r in rows if r.get(f"{name}_seconds") is not None]
        found = sum(1 for r in rows if r.get(f"{name}_rank"))
        errors = sum(1 for r in rows if r.get(f"{name}_error"))
        return {
            "queries": len(rows),
            "found_any_expected": found,
            "recall_at_k": round(found / len(rows), 3),
            "mrr": round(statistics.fmean(1 / r for r in ranks), 3) if ranks else 0.0,
            "mean_rank": round(statistics.fmean(ranks), 2) if ranks else None,
            "mean_seconds": round(statistics.fmean(lat), 3) if lat else None,
            "errors": errors,
        }

    summary = {"bm25": summarise("bm25"), "fts5": summarise("fts5"), "top": args.top,
               "queries_file": str(QUERIES.relative_to(REPO))}
    print("\n== summary ==")
    print(json.dumps(summary, indent=2))
    if args.json:
        print(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
