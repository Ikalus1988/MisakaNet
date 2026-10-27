#!/usr/bin/env python3
"""Measure zh retrieval on the **live** path, split by the target lesson's language.

Why this exists (2026-10-27)
----------------------------
`docs/maintainer/handoff-2026-10-27.md` §2.2 proposed CJK tokenisation as the next Chinese lever,
citing 3/15 (20%) on the 80-sample audit. Two things were wrong with that entry, and both are cheap
to settle with a measurement:

* **CJK tokenisation already shipped.** #2355–#2358 closed in late September; the deployed index
  carries `index.cjk` (see `GET /api/search-index`: `textVersion: 5`, `cjkChannel.version: 1`), and
  `scripts/bench_production_recall.py` reports zh at 12/22 against a floor of 11. The global
  "Chinese is broken" reading is not supportable.
* **"Chinese recall" is two problems.** A Chinese query aimed at an English lesson is
  *cross-lingual*; tokenising CJK better cannot help it, because the target shares no characters.
  Half of the zh queries in the L1-267 query set are this kind (33 of 64), so a single zh number
  averages a problem the CJK channel owns with one it structurally cannot touch.

So this script buckets by the **target lesson's** language and reports the two rates separately.
That is the number the next lever should be chosen from.

What it is not
--------------
* **Not a gate.** It needs the live service, so it is not in CI (same rule as
  `scripts/bench_production_recall.py` and `scripts/compare_search_paths.py`).
* **Not a quality verdict on the lessons.** A miss can be a stale target, a query the model wrote
  poorly, or a real ranking failure. The rows are printed so a human can tell them apart; nothing
  here decides which it was.
* **Not a replacement for the floor bench.** `scripts/bench_production_recall.py` measures the
  repository's 42 fixed queries against the gate's floors. This one measures a larger synthetic set
  bucketed by language. Run both when the question is "did the corpus or the ranker move".

Usage
-----
    python3 scripts/bench_zh_crosslingual.py
    python3 scripts/bench_zh_crosslingual.py --json          # machine-readable
    python3 scripts/bench_zh_crosslingual.py --limit 10      # smoke test
    python3 scripts/bench_zh_crosslingual.py --delay 0       # no pacing (expect 429s)

Transport failures are retried and reported **separately from misses**: a connection reset is not a
retrieval result, and counting it as one is how a flaky network turns into a fake recall number.
(The first run of this probe lost 20 of 64 bodies and would have scored them as misses.)

Two traps that make a hand-rolled probe look like a broken service, both already recorded:

* **The edge 403s Python urllib's default UA.** `Python-urllib/3.x` is refused while `curl` is not
  (`docs/agents/repo-operations.md` §4, 2026-09-28). `USER_AGENT` below is not decoration; without
  it every row "fails" and the table is empty.
* **A local `https_proxy` that drops connections** is indistinguishable from an endpoint serving
  empty bodies. `--noproxy` exists so the two can be told apart instead of argued about.
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
DEFAULT_QUERIES = REPO / "docs" / "benchmarks" / "retrieval-l1-267-queries.jsonl"
DEFAULT_ENDPOINT = "https://misakanet.org/mcp"
# Not decoration: the edge answers `Python-urllib/3.x` with 403 while `curl` gets 200
# (docs/agents/repo-operations.md §4, 2026-09-28). Without this every row fails.
USER_AGENT = "misakanet-bench/1.0 (+https://misakanet.org; zh cross-lingual probe)"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "MCP-Protocol-Version": "2025-06-18",
    "Origin": "https://misakanet.org",
    "User-Agent": USER_AGENT,
}

# A lesson counts as Chinese when CJK characters are more than a quarter of its first block. The
# threshold is deliberately crude: it separates the two populations in the corpus cleanly (English
# lessons with a Chinese title stay under it, Chinese lessons with English code stay over it), and a
# finer classifier would imply a precision this bucket split does not need.
CJK_RATIO_THRESHOLD = 0.25
LANG_SAMPLE_CHARS = 1500


def cjk_ratio(text: str) -> float:
    """Share of CJK characters among non-whitespace characters. Public for the tests."""
    stripped = re.sub(r"\s", "", text or "")
    if not stripped:
        return 0.0
    return sum(1 for ch in stripped if "\u4e00" <= ch <= "\u9fff") / len(stripped)


def lesson_language(path: Path) -> str:
    """`zh` or `en` from the lesson body's own text. Frontmatter is skipped: its tags are English
    even on Chinese lessons, and counting them would push those lessons under the threshold."""
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return "unknown"
    body = raw.split("---", 2)[-1]
    return "zh" if cjk_ratio(body[:LANG_SAMPLE_CHARS]) > CJK_RATIO_THRESHOLD else "en"


def load_queries(path: Path, limit: int | None = None) -> list[dict]:
    """The zh rows of a query set. `lang` is the query's language, which is what we bucket *by*;
    the target's language is what we bucket *into*."""
    rows = []
    with Path(path).open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("lang") == "zh":
                rows.append(row)
    return rows[:limit] if limit else rows


def search_once(endpoint: str, query: str, top: int, timeout: float) -> dict:
    """One tool call. Raises on transport failure so the caller can retry it — an empty body must
    never be scored as `no_match`."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "misakanet_search",
            "arguments": {"query": query, "top": top, "detail": "compact"},
        },
    }
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=HEADERS,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
    envelope = json.loads(body)  # raises ValueError on a truncated body
    result = envelope.get("result") or {}
    structured = result.get("structuredContent")
    if structured:
        return structured
    # Older responses carry the payload as JSON inside content[0].text.
    text = (result.get("content") or [{}])[0].get("text")
    if not text:
        raise ValueError("response carries neither structuredContent nor content[0].text")
    return json.loads(text)


def search(endpoint: str, query: str, top: int, timeout: float, attempts: int) -> tuple[dict | None, int]:
    """Up to `attempts` tries; returns (payload or None, number of tries used)."""
    for attempt in range(1, attempts + 1):
        try:
            return search_once(endpoint, query, top, timeout), attempt
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError):
            if attempt == attempts:
                return None, attempt
            time.sleep(1.5 * attempt)
    return None, attempts


def probe(args: argparse.Namespace) -> dict:
    queries = load_queries(Path(args.queries), args.limit)
    rows: list[dict] = []
    for i, q in enumerate(queries, 1):
        target = lesson_language(REPO / q["target_url"])
        payload, tries = search(args.endpoint, q["query"], args.top, args.timeout, args.attempts)
        if payload is None:
            rec = {
                "lesson_id": q["lesson_id"],
                "target_lang": target,
                "overlap": q.get("overlap_bucket"),
                "query": q["query"],
                "ok": False,
                "tries": tries,
            }
        else:
            ids = [r.get("id") for r in (payload.get("results") or [])]
            rank = ids.index(q["lesson_id"]) + 1 if q["lesson_id"] in ids else None
            rec = {
                "lesson_id": q["lesson_id"],
                "target_lang": target,
                "overlap": q.get("overlap_bucket"),
                "query": q["query"],
                "ids": ids,
                "rank": rank,
                "no_match": bool(payload.get("no_match")),
                "source": payload.get("source"),
                "tries": tries,
                "ok": True,
            }
        rows.append(rec)
        print(
            f"{i}/{len(queries)} zh->{target} rank={rec.get('rank')} "
            f"no_match={rec.get('no_match')} source={rec.get('source')} ok={rec['ok']} tries={tries}",
            file=sys.stderr,
            flush=True,
        )
        if args.delay and i < len(queries):
            time.sleep(args.delay)

    return {"endpoint": args.endpoint, "top": args.top, "rows": rows, "summary": tally(rows)}


def tally(rows: list[dict]) -> dict:
    """Rates per (query-language, target-language) bucket. Transport failures are excluded from the
    denominators and counted in their own field — the whole point of the retry loop is that a
    reset connection never becomes a miss."""
    ok = [r for r in rows if r.get("ok")]
    summary: dict = {
        "n_total": len(rows),
        "transport_failures": len(rows) - len(ok),
        "buckets": {},
    }
    for target in ("zh", "en", "unknown"):
        sub = [r for r in ok if r.get("target_lang") == target]
        if not sub:
            continue
        n = len(sub)
        ranks = [r["rank"] for r in sub]
        misses_with_results = [r for r in sub if r["rank"] is None and r.get("ids")]
        summary["buckets"][f"zh->{target}"] = {
            "n": n,
            "r@1": round(sum(1 for x in ranks if x == 1) / n, 3),
            "r@3": round(sum(1 for x in ranks if x and x <= 3) / n, 3),
            "r@5": round(sum(1 for x in ranks if x and x <= 5) / n, 3),
            "no_match": round(sum(1 for r in sub if r.get("no_match")) / n, 3),
            "semantic_used": round(sum(1 for r in sub if "semantic" in str(r.get("source") or "")) / n, 3),
            # A miss that returned *something* never reaches the semantic fallback: the fallback is
            # gated on an empty BM25 result (`register-proxy-sw.js`, "a hit is never re-ranked").
            "miss_with_results": len(misses_with_results),
            "miss_with_no_results": sum(1 for r in sub if r["rank"] is None and not r.get("ids")),
        }
    for target in ("zh", "en"):
        for overlap in ("high", "low"):
            sub = [r for r in ok if r.get("target_lang") == target and r.get("overlap") == overlap]
            if not sub:
                continue
            n = len(sub)
            summary["buckets"][f"zh->{target}/{overlap}"] = {
                "n": n,
                "r@1": round(sum(1 for r in sub if r["rank"] == 1) / n, 3),
                "no_match": round(sum(1 for r in sub if r.get("no_match")) / n, 3),
            }
    return summary


def render(summary: dict) -> str:
    lines = [
        "live retrieval, zh queries of the L1-267 set",
        f"  transport failures (excluded): {summary['transport_failures']}/{summary['n_total']}",
        "",
        "  bucket            n   R@1    R@3    R@5    no_match  semantic  miss+results  miss+empty",
    ]
    for name, b in summary["buckets"].items():
        if "/" in name:
            continue
        lines.append(
            f"  {name:14s} {b['n']:3d}  {b['r@1']:.3f}  {b['r@3']:.3f}  {b['r@5']:.3f}  "
            f"{b['no_match']:.3f}     {b['semantic_used']:.3f}     {b['miss_with_results']:3d}"
            f"          {b['miss_with_no_results']:3d}"
        )
    overlap = [(n, b) for n, b in summary["buckets"].items() if "/" in n]
    if overlap:
        lines += ["", "  by overlap:", "  bucket              n   R@1    no_match"]
        for name, b in overlap:
            lines.append(f"  {name:18s} {b['n']:3d}  {b['r@1']:.3f}   {b['no_match']:.3f}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--queries", default=str(DEFAULT_QUERIES), help="query set (jsonl with `lang`, `target_url`)")
    ap.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--delay", type=float, default=2.1, help="seconds between queries (default 2.1 ≈ 28/min)")
    ap.add_argument("--timeout", type=float, default=40.0)
    ap.add_argument("--attempts", type=int, default=3, help="transport retries per query")
    ap.add_argument("--limit", type=int, default=None, help="only the first N zh queries (smoke test)")
    ap.add_argument(
        "--noproxy",
        action="store_true",
        help="ignore http(s)_proxy from the environment; a local proxy dropping connections looks "
             "exactly like the endpoint serving empty bodies",
    )
    ap.add_argument("--json", action="store_true", help="machine-readable summary instead of the table")
    ap.add_argument(
        "--out",
        default=None,
        help="also write the full report (summary + every row) to this path — the artifact a report cites",
    )
    args = ap.parse_args(argv)

    if args.noproxy:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        urllib.request.install_opener(opener)

    report = probe(args)
    if args.out:
        Path(args.out).write_text(
            json.dumps({**report, "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
                       ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
    if args.json:
        print(json.dumps(report["summary"], ensure_ascii=False, indent=1))
    else:
        print(render(report["summary"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
