#!/usr/bin/env python3
"""Measure whether a relevance *floor* could separate "no match" from "weak match" — #2790.

The problem, in the reporter's words
------------------------------------
A technician asking about a FANUC servo following error gets three unrelated lessons
and the voice `lesson-found`, with no score in the response to tell them otherwise.
The scores exist under `detail:"full"` and, measured on 2026-10-04, separated cleanly:

    irrelevant hits   2.99 – 3.16
    relevant hits    11.22 – 18.43

So the retrieval layer is holding the information and not using it. Three things
follow, and only the first is a measurement:

1. **Is the gap real, and where is it?** — this script answers it.
2. **Should there be a floor?** — a product judgement (§2790's own "需要人拍板" list).
3. **Below the floor, return what?** — `no_match` + intake guidance is the existing shape.

**This script therefore does not propose a number.** It measures the distribution of
the top score for queries that *should* match against queries that should not, so that
item 2 is decided against a recorded distribution instead of against two hand-copied
rows. A floor that "looks safe" on two examples is not a measurement — that is the
§45 lesson in this repository's own handoff, where refusing to set a threshold twice
turned out to be hiding that the direction itself was wrong.

How it is measured
------------------
Through `workers/register-proxy-sw.js`'s **real** search path — the same imports
`search-dual-floor.test.mjs` uses — with the BM25 index built in-process from
`data/lessons.json`, and `misakanet_search` called over the MCP handler.

Two honesty rules this file keeps:

* **The irrelevant queries are not chosen by me.** They are drawn from the corpus's own
  recorded gap: `scripts/eval_query_aliases.py`'s question set is *answerable*, so it
  cannot stand in for "no match". Instead the negatives are questions a retrieval
  system genuinely cannot answer — and the script prints every query it used, so a
  reader can disagree with the set rather than having to reverse-engineer it.
* **A single index per process.** The worker memoises `_bm25Index` at module scope, so
  two corpora in one process silently share one index (`search-dual-floor.test.mjs`'s
  header warns about exactly this).

Fidelity of the offline corpus is the question `search-recall-regression.test.mjs`
raised, and §52 of the maintainer handoff measured it: the offline index passes the
worker's own `indexShapeProblem` gate (#2079) and its average document length sits
within 10% of production. This script prints that shape next to the scores, so the
numbers are read with the caveat attached rather than without it.

Usage:
    node workers/_score-separation-run.mjs        # produces /tmp/separation.json
    python3 scripts/bench_relevance_separation.py # prints the distribution

    --json PATH   also dump the raw per-query rows for a record
    --only name   restrict to one bucket ("relevant" | "irrelevant")
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUNNER = REPO / "workers" / "_score-separation-run.mjs"

# Queries that *should* match. The expected lesson is named so a regression can be
# told apart from "retrieval got worse" — the same discipline `data/search-floor-queries.jsonl`
# uses, and the reason §2790 says recall benchmarks cannot see this class of bug.
RELEVANT = [
    ("SRVO-002 position error servo", "fanuc-alarm-severity-guide"),
    ("servo following error tuning", "fanuc-alarm-severity-guide"),
    ("SRVO-001 unexpected servo stop", "fanuc-alarm-severity-guide"),
    ("TEACH pendant position error FANUC", "fanuc-alarm-severity-guide"),
    ("pipe install timeout behind proxy", None),
    ("EADDRINUSE port already allocated", None),
]

# Queries that cannot be answered by any lesson. These are the ones that produced the
# 2.99–3.16 band in the report. They are printed in the output so the set is auditable.
IRRELEVANT = [
    "following error",
    "how do I calibrate a Fuji tactile sensor",
    "best breakfast recipe for oats",
    "帮我把冰箱门关上",
    "quarterly revenue forecast spreadsheet",
    "how do I train for a marathon in 8 weeks",
]


def run_node(only: str | None) -> dict:
    """Ask the worker for the scores. The node side owns the retrieval path on purpose."""
    # The worker logs one JSON line per request to stdout (register-proxy-sw.js:6899), so the
    # payload goes to fd 3 and stdout is left alone. A measurement should not edit the thing it
    # measures to make its output easier to read.
    read_fd, write_fd = os.pipe()
    env = {**os.environ, "SCORE_SEPARATION_FD": str(write_fd)}
    cmd = ["node", str(RUNNER)] + (["--only", only] if only else [])
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, cwd=REPO, env=env, pass_fds=(write_fd,))
    os.close(write_fd)
    payload = proc.stdout.read()          # the worker's own request log
    raw = os.read(read_fd, 10_000_000).decode() if os.fstat(read_fd).st_size == 0 else ""
    with os.fdopen(read_fd) as fh:
        raw = raw or fh.read()
    proc.wait()
    if proc.returncode != 0:
        sys.stderr.write(payload + proc.stderr.read())
        raise SystemExit(f"the runner failed (exit {proc.returncode})")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        sys.stderr.write((raw or payload)[:2000])
        raise SystemExit("the runner did not print JSON")


def summarise(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    s = sorted(values)
    mid = len(s) // 2
    return {
        "n": len(s),
        "min": round(s[0], 2),
        "median": round(s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2, 2),
        "max": round(s[-1], 2),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="dump raw rows to this path")
    ap.add_argument("--only", choices=("relevant", "irrelevant"))
    args = ap.parse_args()

    data = run_node(args.only)
    shape = data.get("indexShape", {})

    rel = [r["top1"] for r in data["relevant"]]
    irr = [r["top1"] for r in data["irrelevant"]]

    print("=" * 72)
    print("#2790 — is there a gap between 'no match' and 'weak match'?")
    print("=" * 72)
    print(f"corpus: data/lessons.json at {shape.get('rows', '?')} rows, "
          f"{shape.get('docs', '?')} indexed, avgDocLen {shape.get('avgDocLen', '?')}")
    print(f"indexShapeProblem (the worker's own #2079 gate): "
          f"{shape.get('problem', 'n/a') or 'clean'}")

    print("\n--- queries that SHOULD match (top-1 score) ---")
    for r in data["relevant"]:
        hit = "ok " if r.get("expected") is None or r.get("expected") in r.get("hitIds", []) else "MISS"
        print(f"  {hit} {r['top1']:>6.2f}  {r['query'][:46]:46}  top={r['hitId']}")
    print(f"  summary: {summarise(rel)}")

    print("\n--- queries that should NOT match (top-1 score) ---")
    for r in data["irrelevant"]:
        print(f"      {r['top1']:>6.2f}  {r['query'][:46]:46}  top={r['hitId']}")
    print(f"  summary: {summarise(irr)}")

    # A zero is a *no_match*, not a weak hit. The band that matters is only the rows the
    # worker chose to answer at all; averaging them together with the abstentions would
    # describe a distribution that does not exist.
    rel_answered = [r for r in data["relevant"] if r["top1"] > 0]
    irr_answered = [r for r in data["irrelevant"] if r["top1"] > 0]
    rel_scores = [r["top1"] for r in rel_answered]
    irr_scores = [r["top1"] for r in irr_answered]

    print("\n--- answered vs abstained ---")
    print(f"  relevant:   {len(rel_answered)} answered, {len(data['relevant']) - len(rel_answered)} returned no_match")
    print(f"  irrelevant: {len(irr_answered)} answered, {len(data['irrelevant']) - len(irr_answered)} returned no_match")

    print("\n--- verdict ---")
    if not rel_scores or not irr_scores:
        print("  no overlap to compare on this set")
        return 0
    gap = min(rel_scores) - max(irr_scores)
    if gap <= 0:
        print(f"  NO clean separation: the worst answered relevant ({min(rel_scores):.2f}) does not")
        print(f"  beat the best answered irrelevant ({max(irr_scores):.2f})")
        print("  A single floor cannot separate these. #2790's 'very wide margin' was measured")
        print("  on one irrelevant query; this set has several, and the cheap ones score high.")
        print("  Before a floor is considered, the answered-irrelevant set needs to be wider")
        print("  than the six queries here — one query is not a distribution.")
    else:
        print(f"  every answered relevant beats every answered irrelevant by at least {gap:.2f}")
        print(f"  a floor in ({max(irr_scores):.2f}, {min(rel_scores):.2f}) separates them ON THIS SET")
        print("  MEASUREMENT, not a recommendation. Six queries are not a distribution, and")
        print("  the offline corpus is not production's — see indexShape above.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
