#!/usr/bin/env python3
"""Ask Cloudflare which D1 statement is reading the most rows, before the bill says so.

WHY THIS EXISTS (2026-11-24)
----------------------------
The same class of bug has been fixed twice. 2026-10-21: a prefix enumeration scanned 68,892 rows per
call; the answer was a hand-written replica test (`tests/test_d1_read_hotspots.py`) for that one
query. 2026-11-24: a three-column `OR` join in the contribution ladder read **19,561,754,663 rows in
a month** — 10.4M rows per call, 90% of every row the account read — and no test covered it, because
the pattern only ever covers the queries somebody thought of.

The failure is silent by construction: correct answers, ordinary latency, no error. It surfaces on the
bill, weeks later, at which point the fix has to be found by hand.

This script is the layer that does not need anyone to know in advance which query will hurt. It reads
Cloudflare's own per-query dataset — `d1QueriesAdaptiveGroups`, which carries a `query` dimension, so
`wrangler d1 insights` is not needed — and reports, per statement:

* **rows read per call**, which is what separates a bad *shape* from a busy one;
* total rows, calls, and rows written;
* **what is new since the comparison window**, so one chronic offender does not fill the list forever.

Two windows are kept **in memory** rather than in a committed snapshot: "new" means "in this window's
top list and not in the previous window's", which needs no state file and cannot drift.

Usage::

    CF_ANALYTICS_TOKEN=… python3 scripts/d1_cost_report.py                # yesterday vs the day before
    CF_ANALYTICS_TOKEN=… python3 scripts/d1_cost_report.py --days 7       # a week, vs the week before
    CF_ANALYTICS_TOKEN=… python3 scripts/d1_cost_report.py --check        # exit 1 above threshold
    CF_ANALYTICS_TOKEN=… python3 scripts/d1_cost_report.py --markdown FILE

Exit codes: 0 = nothing over the threshold, 1 = an offender (report says which), 2 = could not read —
which is not the same answer as "all fine", the distinction `doctor.py` and `setup_release_drift.py`
already make.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import urllib.request

GRAPHQL = "https://api.cloudflare.com/client/v4/graphql"
API = "https://api.cloudflare.com/client/v4"

#: A statement reading more than this many rows per call is called out. The measured baseline for the
#: healthy queries on this account is 2–1,600 rows/call; the ladder bug was 10,444,076.
DEFAULT_MAX_ROWS_PER_CALL = 100_000

PER_QUERY = """
query($a:String!,$from:String!,$to:String!,$limit:Int!){
  viewer{ accounts(filter:{accountTag:$a}){
    d1QueriesAdaptiveGroups(limit:$limit, filter:{date_geq:$from, date_leq:$to},
                            orderBy:[sum_rowsRead_DESC]){
      sum{ rowsRead rowsWritten }
      count
      dimensions{ query }
    } } } }"""

PER_DATABASE = """
query($a:String!,$from:String!,$to:String!){
  viewer{ accounts(filter:{accountTag:$a}){
    d1AnalyticsAdaptiveGroups(limit:10, filter:{date_geq:$from, date_leq:$to},
                              orderBy:[sum_rowsRead_DESC]){
      sum{ rowsRead rowsWritten } count dimensions{ databaseId }
    } } } }"""


def _post(token: str, query: str, variables: dict, attempts: int = 3) -> dict:
    """One GraphQL call, with retries.

    Retried because the transport is the flaky part, not the query: measured 2026-11-24 from this
    machine, the same request sometimes ends in `SSL: UNEXPECTED_EOF_WHILE_READING` while `curl` gets
    200 seconds later. A report that fails on that is a report nobody schedules.
    """
    body = json.dumps({"query": query, "variables": variables}).encode()
    last: Exception | None = None
    for _ in range(attempts):
        request = urllib.request.Request(GRAPHQL, data=body, method="POST")
        request.add_header("Authorization", f"Bearer {token}")
        request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 — fixed host
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as error:  # noqa: BLE001 — retry, then surface
            last = error
            continue
        if payload.get("errors"):
            raise RuntimeError(json.dumps(payload["errors"])[:300])
        return payload.get("data") or {}
    raise RuntimeError(f"analytics API unreachable after {attempts} attempts: {last}")


def accounts(token: str, attempts: int = 3) -> list[dict]:
    last: Exception | None = None
    for _ in range(attempts):
        request = urllib.request.Request(API + "/accounts")
        request.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
                payload = json.loads(response.read().decode("utf-8"))
            return payload.get("result") or []
        except Exception as error:  # noqa: BLE001
            last = error
    raise RuntimeError(f"accounts API unreachable after {attempts} attempts: {last}")


def account_id_from(*candidates: str) -> str:
    for value in candidates:
        if value and len(value) == 32 and all(c in "0123456789abcdef" for c in value.lower()):
            return value
    return ""


def normalise(query: str, limit: int = 200) -> str:
    """One line, collapsed whitespace, truncated — the dataset returns the statement verbatim."""
    return " ".join(str(query or "").split())[:limit]


def rows_per_call(rows_read: int, calls: int) -> float:
    return rows_read / calls if calls else 0.0


def classify(entries: list[dict], threshold: int) -> list[dict]:
    """Mark each entry `shape` (too many rows per call) or `busy` (many calls, normal shape)."""
    out = []
    for entry in entries:
        ratio = rows_per_call(entry["rows_read"], entry["calls"])
        out.append({**entry, "rows_per_call": ratio,
                    "verdict": "shape" if ratio > threshold else "busy"})
    return out


def new_since(current: list[dict], previous: list[dict]) -> list[dict]:
    """Entries whose normalised text is absent from the previous window's list."""
    seen = {entry["query"] for entry in previous}
    return [entry for entry in current if entry["query"] not in seen]


def collect(token: str, account: str, start: str, end: str, limit: int = 25) -> list[dict]:
    data = _post(token, PER_QUERY, {"a": account, "from": start, "to": end, "limit": limit})
    accounts_block = (data.get("viewer") or {}).get("accounts") or [{}]
    rows = (accounts_block[0] or {}).get("d1QueriesAdaptiveGroups") or []
    return [{
        "query": normalise((row.get("dimensions") or {}).get("query")),
        "rows_read": int((row.get("sum") or {}).get("rowsRead") or 0),
        "rows_written": int((row.get("sum") or {}).get("rowsWritten") or 0),
        "calls": int(row.get("count") or 0),
    } for row in rows]


def database_totals(token: str, account: str, start: str, end: str) -> list[dict]:
    data = _post(token, PER_DATABASE, {"a": account, "from": start, "to": end})
    accounts_block = (data.get("viewer") or {}).get("accounts") or [{}]
    rows = (accounts_block[0] or {}).get("d1AnalyticsAdaptiveGroups") or []
    return [{
        "database": (row.get("dimensions") or {}).get("databaseId", "?"),
        "rows_read": int((row.get("sum") or {}).get("rowsRead") or 0),
        "rows_written": int((row.get("sum") or {}).get("rowsWritten") or 0),
        "calls": int(row.get("count") or 0),
    } for row in rows]


def render_markdown(report: dict) -> str:
    lines = [f"# D1 cost — {report['window']['from']}…{report['window']['to']}", ""]
    if report.get("totals"):
        lines += ["| database | reads | writes | calls |", "|---|---|---|---|"]
        for row in report["totals"]:
            lines.append(f"| `{row['database']}` | {row['rows_read']:,} | "
                         f"{row['rows_written']:,} | {row['calls']:,} |")
        lines.append("")
    offenders = [entry for entry in report["entries"] if entry["verdict"] == "shape"]
    if offenders:
        lines += ["## Statements whose *shape* costs rows", "",
                  "| rows/call | calls | reads | statement |", "|---|---|---|---|"]
        for entry in offenders:
            lines.append(f"| **{entry['rows_per_call']:,.0f}** | {entry['calls']:,} | "
                         f"{entry['rows_read']:,} | `{entry['query'][:110]}` |")
        lines.append("")
    if report["new"]:
        lines += ["## New since the comparison window", ""]
        for entry in report["new"]:
            lines.append(f"- {entry['rows_per_call']:,.0f} rows/call · {entry['calls']:,} calls · "
                         f"`{entry['query'][:110]}`")
        lines.append("")
    if not offenders and not report["new"]:
        lines += ["No statement is over the threshold and nothing is new.", ""]
    lines += ["Read from Cloudflare's `d1QueriesAdaptiveGroups`; rows/call is the number that tells a "
              "bad shape from a busy query. See `docs/maintainer/d1-cost.md`."]
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--days", type=int, default=1, help="window length, ending yesterday (1)")
    parser.add_argument("--end", default=None,
                        help="last day of the window, YYYY-MM-DD (default: yesterday — a partial day "
                             "reports a partial count, which is fine for a look and wrong for a gate)")
    parser.add_argument("--max-rows-per-call", type=int, default=DEFAULT_MAX_ROWS_PER_CALL)
    parser.add_argument("--limit", type=int, default=25, help="statements to read per window")
    parser.add_argument("--account", default=os.environ.get("CF_ACCOUNT_ID", ""),
                        help="account id (default: CF_ACCOUNT_ID, else the first account the token sees)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--markdown", type=argparse.FileType("w", encoding="utf-8"))
    parser.add_argument("--check", action="store_true", help="exit 1 when a statement is over the "
                                                            "threshold or is new")
    args = parser.parse_args(argv)

    token = os.environ.get("CF_ANALYTICS_TOKEN", "").strip()
    if not token:
        print("CF_ANALYTICS_TOKEN is not set — this report reads Cloudflare's analytics API, and it "
              "needs a token with Account Analytics: Read", file=sys.stderr)
        return 2

    account = account_id_from(args.account)
    if not account:
        found = accounts(token)
        if not found:
            print("no account visible to this token", file=sys.stderr)
            return 2
        account = str(found[0].get("id") or "")
        if not account:
            return 2

    today = dt.date.today()
    end = dt.date.fromisoformat(args.end) if args.end else today - dt.timedelta(days=1)
    start = end - dt.timedelta(days=args.days - 1)
    prev_end = start - dt.timedelta(days=1)
    prev_start = prev_end - dt.timedelta(days=args.days - 1)

    try:
        current = collect(token, account, start.isoformat(), end.isoformat(), args.limit)
        previous = collect(token, account, prev_start.isoformat(), prev_end.isoformat(), args.limit)
        totals = database_totals(token, account, start.isoformat(), end.isoformat())
    except Exception as error:  # noqa: BLE001 — the exit code carries the distinction
        print(f"could not read Cloudflare analytics: {type(error).__name__}: {error}", file=sys.stderr)
        return 2

    report = {
        "window": {"from": start.isoformat(), "to": end.isoformat(), "days": args.days},
        "compared_with": {"from": prev_start.isoformat(), "to": prev_end.isoformat()},
        "threshold": args.max_rows_per_call,
        "entries": classify(current, args.max_rows_per_call),
        "new": classify(new_since(current, classify(previous, args.max_rows_per_call)),
                        args.max_rows_per_call),
        "totals": totals,
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        markdown = render_markdown(report)
        if args.markdown:
            args.markdown.write(markdown)
            print(f"wrote {args.markdown.name}")
        else:
            print(markdown)

    offenders = [entry for entry in report["entries"] if entry["verdict"] == "shape"]
    if args.check and (offenders or report["new"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
