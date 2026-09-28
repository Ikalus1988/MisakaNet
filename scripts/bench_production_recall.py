#!/usr/bin/env python3
"""Run the repository's own retrieval bench against the **live** service, next to the gate's floors.

Why this exists (2026-09-28)
----------------------------
`workers/search-dual-floor.test.mjs` is the gate: 20 English + 22 CJK queries, floored at 16/19 and
11/15, driven through the real MCP handler over `data/lessons.json` — 418 rows when those floors were
last raised. It runs in CI, and it measures *the repository's* corpus.

Production is not that corpus. The same 42 queries against `https://misakanet.org/mcp` on 2026-09-28
scored:

    English  hit1 13/20  hit3 18/20     (gate: 16/19)
    CJK      hit1 11/22  hit3 14/22     (gate: 11/15)

with production serving 426 rows in `textMode: rich` (the D1 `problem/root_cause/solution/verification`
projection) while the gate builds its index from `summary` + `preview`. Neither side is wrong. What was
wrong is that the difference was invisible: the floors read as "what search does", and comparing them
took a hand-written probe — one that first returned `403` on every row because of a user-agent rule
(#2419) and had to be re-run.

So this script prints both sides at once, **and the corpus sizes that explain the gap**, so the confound
is in the output rather than in someone's head.

What it is not
--------------
* **Not a gate.** It needs the live service, so it is not in CI (same rule as
  `scripts/compare_search_paths.py`). Its exit code is a *signal for a human*: `1` means the live
  service scored below the gate's floor, which is either the corpus/projection difference printed above
  it or a real regression — deciding which needs reading `data/lessons.json` against the D1 corpus.
* **Not a way to move the floors.** The gate's numbers come from the gate's corpus; lowering them to
  match production would delete the measurement instead of the gap.

Usage
-----
    python3 scripts/bench_production_recall.py                # human-readable table
    python3 scripts/bench_production_recall.py --json         # machine-readable
    python3 scripts/bench_production_recall.py --top 5        # rank window (default 3, the gate's)
    python3 scripts/bench_production_recall.py --delay 0      # no pacing between queries
    python3 scripts/bench_production_recall.py --timeout 60 --attempts 5   # a slow or flaky path

Pacing: the anonymous read path has a burst guard per address (see AGENTS.md §3.3), and a real client
cannot rotate `CF-Connecting-IP` the way the loopback tests do. 42 queries at the default 1.5 s is
~65 s; a `429` is retried with backoff instead of being counted as a miss.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BENCH = REPO / "workers" / "search-dual-floor.test.mjs"
QUERIES = REPO / "data" / "search-floor-queries.jsonl"
REPO_CORPUS = REPO / "data" / "lessons.json"
MCP_URL = "https://misakanet.org/mcp"
INDEX_URL = "https://misakanet.org/api/search-index"
# Measured 2026-09-28: `Python-urllib/3.x` is refused with 403 by the edge; any explicit UA is served.
# See the row added to `docs/agents/repo-operations.md` §4 (#2419).
USER_AGENT = "misakanet-bench/1.0 (+https://misakanet.org; production recall bench)"
LANGUAGES = ("en", "zh")
FLOOR_RE = re.compile(r"export const (EN_FLOOR|ZH_FLOOR) = \{ hit1: (\d+), hit3: (\d+) \};")


def load_rows(path: Path = QUERIES) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_floors(path: Path = BENCH) -> dict[str, dict[str, int]]:
    """The gate's floors, read from the gate.

    Parsed rather than copied: a second copy of these four numbers is a copy that drifts, and the
    same pattern is already how `tests/test_search_floor_queries_schema.py` reads them.
    """
    found = {name: {"hit1": int(hit1), "hit3": int(hit3)}
             for name, hit1, hit3 in FLOOR_RE.findall(path.read_text(encoding="utf-8"))}
    if set(found) != {"EN_FLOOR", "ZH_FLOOR"}:
        raise SystemExit(f"the bench no longer declares both floors in the shape this reads: {sorted(found)}")
    return {"en": found["EN_FLOOR"], "zh": found["ZH_FLOOR"]}


def mcp_search(query: str, top: int, timeout: int = 30, attempts: int = 3) -> dict:
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                          "params": {"name": "misakanet_search",
                                     "arguments": {"query": query, "top": top}}}).encode()
    last = ""
    for attempt in range(attempts):
        request = urllib.request.Request(MCP_URL, data=payload, method="POST", headers={
            "Content-Type": "application/json", "Accept": "application/json",
            "MCP-Protocol-Version": "2025-06-18", "Origin": "https://misakanet.org",
            "User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            last = f"HTTP {error.code}"
            if error.code in (429, 500, 502, 503, 522, 524):
                time.sleep(5 + attempt * 5)
                continue
            return {"ids": [], "no_match": True, "error": last}
        except Exception as error:                                   # noqa: BLE001 — network flake
            last = f"{type(error).__name__}: {error}"
            time.sleep(3 + attempt * 3)
            continue
        if "result" not in body:
            return {"ids": [], "no_match": True, "error": json.dumps(body)[:200]}
        payload_text = json.loads(body["result"]["content"][0]["text"])
        return {"ids": [item["id"] for item in payload_text.get("results", [])],
                "no_match": bool(payload_text.get("no_match")),
                "source": payload_text.get("source")}
    return {"ids": [], "no_match": True, "error": f"gave up: {last}"}


def tally(rows: list[dict], results: dict[str, dict], top: int = 3) -> dict[str, dict]:
    """hit1 / hit3 / misses per language. A hit is "any expected lesson inside the rank window"."""
    out: dict[str, dict] = {}
    for row in rows:
        bucket = out.setdefault(row["language"], {"total": 0, "hit1": 0, "hit3": 0, "misses": [], "errors": []})
        bucket["total"] += 1
        result = results.get(row["id"], {})
        ids = result.get("ids", [])
        rank = next((i for i, lesson_id in enumerate(ids) if lesson_id in row["expected"]), -1)
        if rank == 0:
            bucket["hit1"] += 1
        if 0 <= rank < top:
            bucket["hit3"] += 1
        else:
            bucket["misses"].append({
                "query": row["query"], "language": row["language"],
                "got": ids[:top], "expected": row["expected"], "no_match": result.get("no_match", False)})
        if result.get("error"):
            bucket["errors"].append({"query": row["query"], "error": result["error"]})
    return out


def compare(tallies: dict[str, dict], floors: dict[str, dict]) -> dict[str, dict]:
    """Live numbers against the gate's floors, per language.

    A language with no rows is reported as **below** the floor rather than as met: these are counts, and
    a floor over an empty set is satisfied trivially. (`tests/test_search_floor_queries_schema.py`
    already refuses a bench with fewer than 20 rows per language, but this script's job is to notice
    that state, not to assume it away.)
    """
    out = {}
    for language in LANGUAGES:
        live = tallies.get(language) or {}
        total = live.get("total", 0)
        hit1 = live.get("hit1", 0)
        hit3 = live.get("hit3", 0)
        floor = floors[language]
        out[language] = {
            "total": total, "hit1": hit1, "hit3": hit3,
            "floor_hit1": floor["hit1"], "floor_hit3": floor["hit3"],
            "delta_hit1": hit1 - floor["hit1"], "delta_hit3": hit3 - floor["hit3"],
            "below_floor": total == 0 or hit1 < floor["hit1"] or hit3 < floor["hit3"],
        }
    return out


def live_index(timeout: int = 30) -> dict:
    """What production says about its own corpus and index — the confound, printed with the numbers."""
    request = urllib.request.Request(INDEX_URL, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception as error:                                       # noqa: BLE001 — network flake
        return {"error": f"{type(error).__name__}: {error}"}
    return {key: data.get(key) for key in
            ("docCount", "textMode", "textVersion", "expectedTextVersion", "textVersionCurrent",
             "cjkChannel", "builtAt")}


def render(comparison: dict[str, dict], tallies: dict[str, dict], index: dict, repo_count: int,
           floors: dict[str, dict], measured_on: str) -> str:
    lines = ["bench vs production", f"  gate floors measured on {measured_on}"]
    repo_line = f"  repository corpus: {repo_count} rows ({REPO_CORPUS.name}, the gate's corpus)"
    lines.append(repo_line)
    if "error" in index:
        lines.append(f"  live service: index unavailable ({index['error']})")
    else:
        channel = index.get("cjkChannel")
        channel_text = (f"{channel['termCount']} bigrams over {channel['docCount']} docs"
                        if channel else "none published")
        lines.append(f"  live service: {index.get('docCount')} rows, textMode {index.get('textMode')}, "
                     f"textVersion {index.get('textVersion')} (expected {index.get('expectedTextVersion')}), "
                     f"CJK channel {channel_text}")
    lines.append("")
    lines.append(f"  {'language':9} {'rows':>4} {'live hit1':>9} {'floor':>6} {'live hit3':>9} {'floor':>6}")
    for language in LANGUAGES:
        row = comparison[language]
        lines.append(f"  {language:9} {row['total']:>4} {row['hit1']:>4}/{row['total']:<4} "
                     f"{row['floor_hit1']:>6} {row['hit3']:>4}/{row['total']:<4} {row['floor_hit3']:>6}"
                     + ("   ← below the floor" if row["below_floor"] else ""))
    misses = [miss for language in LANGUAGES for miss in tallies.get(language, {}).get("misses", [])]
    if misses:
        lines.append("")
        lines.append(f"  misses ({len(misses)}) — a production miss is not automatically a regression:")
        for miss in misses:
            lines.append(f"    [{'NONE' if miss['no_match'] else 'MISS'}] {miss['query']}")
            lines.append(f"           got      {miss['got']}")
            lines.append(f"           expected {miss['expected']}")
    errors = [error for language in LANGUAGES for error in tallies.get(language, {}).get("errors", [])]
    if errors:
        lines.append("")
        lines.append(f"  transport errors ({len(errors)}) — these lower the numbers above:")
        for error in errors:
            lines.append(f"    {error['query']}: {error['error']}")
    lines.append("")
    lines.append("  The gate's floors are measured over the repository corpus; this run is against the live")
    lines.append("  service. Read the two corpus lines above before calling a difference a regression.")
    return "\n".join(lines)


def measured_on(path: Path = BENCH) -> str:
    match = re.search(r"export const MEASURED_ON = '([^']+)'", path.read_text(encoding="utf-8"))
    return match.group(1) if match else "(unknown)"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--top", type=int, default=3, help="rank window; the gate counts top-3")
    parser.add_argument("--delay", type=float, default=1.5, help="seconds between queries (burst guard)")
    # A flaky path turns a 90-second run into a long one: each transport failure waits out `--timeout`
    # before retrying, so both knobs are exposed rather than buried.
    parser.add_argument("--timeout", type=int, default=30, help="per-request timeout in seconds")
    parser.add_argument("--attempts", type=int, default=3, help="attempts per query before it is an error")
    parser.add_argument("--json", action="store_true", help="print the comparison as JSON")
    args = parser.parse_args(argv)

    rows = load_rows()
    floors = load_floors()
    results: dict[str, dict] = {}
    for position, row in enumerate(rows):
        results[row["id"]] = mcp_search(row["query"], args.top, timeout=args.timeout, attempts=args.attempts)
        if args.delay and position < len(rows) - 1:
            time.sleep(args.delay)

    tallies = tally(rows, results, args.top)
    comparison = compare(tallies, floors)
    index = live_index()
    repo_count = len(json.loads(REPO_CORPUS.read_text(encoding="utf-8")))

    if args.json:
        print(json.dumps({"comparison": comparison, "index": index, "repo_corpus_rows": repo_count,
                          "floors_measured_on": measured_on(),
                          "misses": {language: tallies.get(language, {}).get("misses", []) for language in LANGUAGES},
                          "errors": {language: tallies.get(language, {}).get("errors", []) for language in LANGUAGES}},
                         ensure_ascii=False, indent=2))
    else:
        print(render(comparison, tallies, index, repo_count, floors, measured_on()))

    return 1 if any(comparison[language]["below_floor"] for language in LANGUAGES) else 0


if __name__ == "__main__":
    sys.exit(main())
