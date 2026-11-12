#!/usr/bin/env python3
"""Two read-only panels on question recurrence — the closest thing to "did it stick?" we can measure.

A retrieval is a lesson that was *fetched*; fetched is not fixed, and nothing here records whether
the caller's problem went away. What the data does show is **whether the same question came back**,
and it has to be read as two different things (#4634):

* **A — answered repeats.** `search_signals` (the live table lives in `misakanet-ops`, not the main
  database: the main copy stopped on 2026-10-26, see #4640/#4696) records each search with its
  normalized query, the lesson it hit (`top_id`) and when. A query that reappears on a **later day**
  with the same `top_id` is a repeat after an answer. The rate is an **upper bound**: without an
  identifier, "the same person came back because the lesson did not help" and "a different person
  asked the same thing" are the same observation.
* **B — unanswered repeats.** `counters(scope='gap')` in the same telemetry database holds one row
  per normalized query per day for queries that hit nothing. A gap bucket seen on **two or more
  days** is someone hitting the same wall again — or two someones. (The main database has a
  same-named `counters` table that stopped during 2026-10-27; reading it returns the gap history up
  to that date and no error, see #4696.)

Neither number is a help metric, and neither is a failure rate. They exist so the digest has a
measured "recurrence" number instead of an invented one.

Read-only by construction: this script only runs `SELECT`s through `wrangler d1 execute --remote`;
it does not touch the worker, the client, or any write path.

    python3 scripts/recurrence_report.py                    # both panels, 7-day window
    python3 scripts/recurrence_report.py --json             # machine-readable
    python3 scripts/recurrence_report.py --days 30
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
#: Both panels read the telemetry database: `search_signals` and `counters` are written by the
#: worker through `opsD1(env)`, and the main database's same-named copies are frozen (#4696).
OPS_DB = "misakanet-ops"

#: A — answered repeats, from the live `search_signals` table (ops).
A_SQL = """WITH solved AS (
  SELECT LOWER(TRIM(query)) AS q, top_id, date(created_at) AS day
    FROM search_signals
   WHERE solved = 1 AND query IS NOT NULL AND TRIM(query) <> ''
     AND created_at >= datetime(date('now','-{days} days'))
)
SELECT
  (SELECT COUNT(DISTINCT q) FROM solved) AS distinct_queries,
  (SELECT COUNT(*) FROM (
     SELECT q, top_id FROM solved
      GROUP BY q, top_id
     HAVING COUNT(DISTINCT day) >= 2
   )) AS repeated_pairs,
  (SELECT MAX(created_at) FROM search_signals) AS newest;"""

#: B — unanswered repeats, from the counters table in the telemetry database (ops).
B_SQL = """SELECT
  (SELECT COUNT(*) FROM (SELECT bucket FROM counters WHERE scope = 'gap' GROUP BY bucket)) AS buckets_total,
  (SELECT COUNT(*) FROM (
     SELECT bucket FROM counters WHERE scope = 'gap'
      GROUP BY bucket HAVING COUNT(DISTINCT period) >= 2
   )) AS repeated_buckets,
  (SELECT COUNT(*) FROM counters WHERE scope = 'gap') AS bucket_days,
  (SELECT MAX(period) FROM counters WHERE scope = 'gap') AS newest;"""


def result_rows(stdout: str) -> list[dict]:
    """Rows from either `wrangler ... --json` envelope (`[{results: [...]}]` or a bare array)."""
    try:
        payload = json.loads(stdout or "")
    except json.JSONDecodeError:
        return []
    if isinstance(payload, dict):
        payload = payload.get("results") or payload.get("result") or []
    if isinstance(payload, list) and payload and isinstance(payload[0], dict) and "results" in payload[0]:
        rows: list[dict] = []
        for chunk in payload:
            rows.extend(chunk.get("results") or [])
        return rows
    return payload if isinstance(payload, list) else []


def _rate(part: int, whole: int) -> float | None:
    return (part / whole) if whole else None


def panels(a_row: dict | None, b_row: dict | None) -> dict:
    """The two readings, with their denominators, rates and newest-row stamps."""
    a = {
        "distinct_queries": int((a_row or {}).get("distinct_queries") or 0),
        "repeated_pairs": int((a_row or {}).get("repeated_pairs") or 0),
        "newest": (a_row or {}).get("newest"),
    }
    a["rate"] = _rate(a["repeated_pairs"], a["distinct_queries"])
    b = {
        "buckets_total": int((b_row or {}).get("buckets_total") or 0),
        "repeated_buckets": int((b_row or {}).get("repeated_buckets") or 0),
        "bucket_days": int((b_row or {}).get("bucket_days") or 0),
        "newest": (b_row or {}).get("newest"),
    }
    b["rate"] = _rate(b["repeated_buckets"], b["buckets_total"])
    return {"answered_repeats": a, "unanswered_repeats": b}


def _age_days(newest: object) -> int | None:
    if not newest:
        return None
    try:
        return (date.today() - date.fromisoformat(str(newest)[:10])).days
    except ValueError:
        return None


def render(result: dict, days: int) -> list[str]:
    a, b = result["answered_repeats"], result["unanswered_repeats"]

    def pct(rate: float | None) -> str:
        return "—" if rate is None else f"{rate * 100:.1f}%"

    lines = [
        f"# Question recurrence — last {days} days",
        "",
        "Both panels are read-only aggregates. Neither is a help metric: a repeat is an upper bound "
        "(different people asking the same thing and one person returning are the same observation), "
        "and a non-repeat does not mean the fix worked.",
        "",
        "## A · answered repeats (`search_signals`, `misakanet-ops`)",
        "",
        f"- distinct normalized solved queries: **{a['distinct_queries']}**",
        f"- reappeared on a later day **with the same lesson**: **{a['repeated_pairs']}**",
        f"- `recurrence_rate = {a['repeated_pairs']} / {a['distinct_queries']} = {pct(a['rate'])}`",
    ]
    age = _age_days(a["newest"])
    if a["newest"] and age is not None and age > 2:
        lines.append(f"- ⚠️ newest row `{a['newest']}` is **{age} days old** — the rate describes that table, not today")
    elif a["newest"]:
        lines.append(f"- newest row: `{a['newest']}`")
    lines += [
        "",
        "## B · unanswered repeats (`counters` scope=gap, `misakanet-ops`)",
        "",
        f"- gap buckets: **{b['buckets_total']}** over **{b['bucket_days']}** bucket-days",
        f"- seen on two or more days: **{b['repeated_buckets']}**",
        f"- `gap_recurrence_rate = {b['repeated_buckets']} / {b['buckets_total']} = {pct(b['rate'])}`",
    ]
    age = _age_days(b["newest"])
    if b["newest"] and age is not None and age > 2:
        lines.append(f"- ⚠️ newest bucket day `{b['newest']}` is **{age} days old**")
    return lines


def wrangler_json(database: str, sql: str) -> list[dict]:
    result = subprocess.run(
        ["wrangler", "d1", "execute", database, "--remote", "--json", "--command", sql],
        cwd=REPO_ROOT / "workers", capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"wrangler failed for {database}: {(result.stderr or result.stdout)[:400]}")
    return result_rows(result.stdout)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--days", type=int, default=7, help="window for the answered-repeat panel")
    ap.add_argument("--ops-db", default=OPS_DB,
                    help=f"database that owns the live search_signals and counters (default {OPS_DB})")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    a_rows = wrangler_json(args.ops_db, A_SQL.replace("{days}", str(args.days)))
    b_rows = wrangler_json(args.ops_db, B_SQL)
    result = panels(a_rows[0] if a_rows else None, b_rows[0] if b_rows else None)
    result["window_days"] = args.days
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("\n".join(render(result, args.days)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
