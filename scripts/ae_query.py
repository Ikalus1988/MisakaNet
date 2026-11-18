#!/usr/bin/env python3
"""Read the `misakanet_events` Analytics Engine dataset — three questions, nothing else.

Why this exists
---------------
The worker writes one Analytics Engine data point per completed MCP tool call (see the schema in
`workers/register-proxy-sw.js`). This script is the read side: it asks the three questions the
heartbeat panel was missing before that dataset existed.

  1. **Miss rate** — `no_match` searches divided by all completed searches.
  2. **p95 latency** — the 95th percentile of served milliseconds, per tool.
  3. **Top 10 hashed queries with no hits** — the `query_hash` values that missed most often.

It answers those and nothing else. A query text is never available here because the worker never
writes one: the dataset stores a stable SHA-256 prefix, so this report can say "the same query
missed 14 times" without being able to say what the query was.

Credentials
-----------
`CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`, read from the environment only (never
arguments, never a file in the repository). The token needs **Account | Account Analytics | Read**.
It is sent only in the `Authorization` header, is never placed in the URL or query body, and is
never printed — not even on an error path.

The Analytics Engine SQL API is at:
`https://api.cloudflare.com/client/v4/accounts/{account_id}/analytics_engine/sql`.

Sampling
--------
Analytics Engine samples at high volume and exposes the factor as `_sample_interval`. Counts here
are `SUM(_sample_interval)` and the percentile is `quantileExactWeighted(0.95)(double1,
_sample_interval)`, the forms the Workers Analytics Engine SQL reference documents, so the three
answers stay correct once the dataset is big enough to sample.

Usage
-----
    python3 scripts/ae_query.py              # last 7 days
    python3 scripts/ae_query.py --days 30

Exit codes: `0` the report was printed, `1` the API failed, `2` a credential or argument is missing.
No network happens when the credentials are absent, which is what makes the test stub sufficient.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request

DATASET = "misakanet_events"
DEFAULT_DAYS = 7
MAX_DAYS = 90
ENDPOINT = "https://api.cloudflare.com/client/v4/accounts/{account_id}/analytics_engine/sql"
_ACCOUNT_ID = re.compile(r"[0-9a-fA-F]{32}")


class AnalyticsError(Exception):
    """A safe-to-print failure. Never carries the credential."""


def _window(days: int) -> str:
    """The SQL interval literal, after checking the only thing that goes into the SQL text."""
    if not isinstance(days, int) or isinstance(days, bool) or not 1 <= days <= MAX_DAYS:
        raise AnalyticsError(f"--days must be an integer between 1 and {MAX_DAYS}")
    return f"INTERVAL '{days}' DAY"


def miss_rate_sql(days: int = DEFAULT_DAYS) -> str:
    """Question 1: completed searches, misses, and the ratio between them."""
    return (
        "SELECT "
        "SUM(_sample_interval) AS searches, "
        "SUM(_sample_interval * double3) AS misses, "
        # Both branches must be the same type: Analytics Engine rejects `if(x = 0, 0, <double>)`
        # with "the 2nd and 3rd arguments to IF() must have the same type". Measured live
        # 2026-11-15 against the real dataset, not inferred from the docs.
        "if(SUM(_sample_interval) = 0, 0.0, "
        "SUM(_sample_interval * double3) / SUM(_sample_interval)) AS miss_rate "
        f"FROM {DATASET} "
        f"WHERE timestamp > NOW() - {_window(days)} "
        "AND blob1 = 'misakanet_search'"
    )


def latency_sql(days: int = DEFAULT_DAYS) -> str:
    """Question 2: p95 of `double1`, per tool, with sampled rows weighted by their interval."""
    return (
        "SELECT blob1 AS tool, "
        "quantileExactWeighted(0.95)(double1, _sample_interval) AS p95_ms "
        f"FROM {DATASET} "
        f"WHERE timestamp > NOW() - {_window(days)} "
        "GROUP BY blob1 "
        # `ORDER BY blob1` after `SELECT blob1 AS tool` is rejected ("unable to find type of
        # column: blob1"); the alias is what the planner can still resolve. Verified live.
        "ORDER BY tool"
    )


def top_missed_sql(days: int = DEFAULT_DAYS) -> str:
    """Question 3: the ten hashed queries with the most no-match rows."""
    return (
        "SELECT blob3 AS query_hash, "
        "SUM(_sample_interval) AS misses "
        f"FROM {DATASET} "
        f"WHERE timestamp > NOW() - {_window(days)} "
        "AND blob1 = 'misakanet_search' "
        "AND double3 = 1 "
        "AND blob3 <> '' "
        "GROUP BY blob3 "
        # Same as the latency query: order by the alias, not by the aggregate expression.
        "ORDER BY misses DESC "
        "LIMIT 10"
    )


def phase_sql(days: int = DEFAULT_DAYS) -> str:
    """Question 4: where a search spends its milliseconds, as p95 per phase.

    The endpoint is bimodal from the outside — 1.1 s warm against 4–8.6 s cold, hits and misses
    alike (measured 2026-11-15) — and a client cannot tell the memoised corpus read from the KV
    BM25 index from scoring. `double4..double7` are those phases, written by `recordSearchAnalytics`
    since that measurement.

    **`AND double4 > 0` is load-bearing, not tidiness.** Pre-deploy rows carry zeros in all four
    columns, and a p95 over a day where those rows are the overwhelming majority is 0 — so the
    query as first shipped answered "0 ms" for all four phases while five rows in the same window
    carried real numbers (measured 2026-11-15, minutes after the deploy). A percentile cannot say
    "this row has no measurement"; `count() AS phased_rows` is how the report says how many rows
    the percentiles are standing on.
    """
    return (
        "SELECT "
        "count() AS phased_rows, "
        "quantileExactWeighted(0.95)(double4, _sample_interval) AS lessons_p95, "
        "quantileExactWeighted(0.95)(double5, _sample_interval) AS index_p95, "
        "quantileExactWeighted(0.95)(double6, _sample_interval) AS score_p95, "
        "quantileExactWeighted(0.95)(double7, _sample_interval) AS semantic_p95 "
        f"FROM {DATASET} "
        f"WHERE timestamp > NOW() - {_window(days)} "
        "AND blob1 = 'misakanet_search' "
        "AND double4 > 0"
    )


def intake_coverage_sql(days: int = DEFAULT_DAYS) -> str:
    """Question 5: of the intakes that became issues, how many the corpus already matched.

    The queue grows ~35 filed a day against ~2 triaged on a quiet day, and the only moment both the
    submission and the corpus are in one place is before the issue exists. `findCoveringLesson`
    (#1526) already refuses a `missing_lesson` whose text a lesson covers near-verbatim; it never
    looks at `question`, which is the kind that piles up. So `double2` on the intake point records
    the BM25 hit count at submit time for **every** filing: `countIf(double2 > 0)` is the share a
    submit-side gate could have stopped, `countIf(double2 < 0)` is the share nobody could measure
    (cold isolate), and the last two columns split it by `blob6` (intake_kind) so the question queue can be judged
    separately from the lesson queue.

    **Read only the window after the deploy that introduced the probe (2026-11-18).** Rows written
    before it carry `double2 = 0`, which this query would count as "corpus did not match" — the same
    number a measured zero produces. Baseline on the first night: 48 filed, 20 of them questions, all
    48 in the pre-probe shape.
    """
    return (
        "SELECT "
        "countIf(blob4 = 'new') AS filed, "
        "countIf(blob4 = 'new' AND double2 > 0) AS covered, "
        "countIf(blob4 = 'new' AND double2 < 0) AS unmeasured, "
        "countIf(blob4 = 'new' AND blob6 = 'question') AS questions, "
        "countIf(blob4 = 'new' AND blob6 = 'question' AND double2 > 0) AS questions_covered "
        f"FROM {DATASET} "
        f"WHERE timestamp > NOW() - {_window(days)} "
        "AND blob1 = 'misakanet_submit_intake'"
    )


def build_request(sql: str, *, account_id: str, token: str) -> urllib.request.Request:
    """The POST the SQL API expects. The token lives in the header and nowhere else."""
    account = str(account_id or "").strip()
    secret = str(token or "").strip()
    if not _ACCOUNT_ID.fullmatch(account):
        raise AnalyticsError(
            "CLOUDFLARE_ACCOUNT_ID must be the 32-character account id (lowercase or uppercase hex)"
        )
    if not secret:
        raise AnalyticsError("CLOUDFLARE_API_TOKEN is not set")
    if not isinstance(sql, str) or not sql.strip():
        raise AnalyticsError("the SQL body is empty")
    return urllib.request.Request(
        ENDPOINT.format(account_id=account.lower()),
        data=sql.encode("utf-8"),
        headers={
            "Authorization": f"Bearer {secret}",
            "Content-Type": "text/plain; charset=utf-8",
            "User-Agent": "misakanet-ae-query/1.0",
        },
        method="POST",
    )


def parse_response(raw: object) -> list[dict]:
    """`{"data": [...]}` from the SQL API, or a safe error."""
    if hasattr(raw, "read"):
        raw = raw.read()
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise AnalyticsError("the SQL API answered non-UTF-8 bytes") from exc
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise AnalyticsError("the SQL API answer was not JSON") from exc
    if not isinstance(payload, dict):
        raise AnalyticsError("the SQL API answer was not a JSON object")
    data = payload.get("data")
    if not isinstance(data, list):
        errors = payload.get("errors")
        detail = ""
        if isinstance(errors, list) and errors:
            detail = ": " + "; ".join(str(item) for item in errors[:2])
        raise AnalyticsError(f"the SQL API answer had no data rows{detail}")
    return [row for row in data if isinstance(row, dict)]


def run_query(
    sql: str, *, account_id: str, token: str, opener, timeout: float = 30.0
) -> list[dict]:
    """One POST, one parsed row list. `opener` is injectable so the test can stay offline."""
    request = build_request(sql, account_id=account_id, token=token)
    try:
        response = opener(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        # Deliberately not `str(exc)`: the message is already safe, but the rule is simple enough to
        # keep the token out of every f-string rather than audit each one.
        raise AnalyticsError(f"Analytics Engine SQL API returned HTTP {exc.code}") from None
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", "network error")
        raise AnalyticsError(f"could not reach the Analytics Engine SQL API: {reason}") from None
    except OSError as exc:
        raise AnalyticsError(f"the SQL API request failed: {exc}") from None
    return parse_response(response)


def _as_float(value: object) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if number == number else None  # NaN is not an answer


def _format_count(value: object) -> str:
    number = _as_float(value)
    if number is None:
        return "0"
    return str(int(number)) if number.is_integer() else f"{number:.2f}"


def build_report(
    miss_rows: list[dict],
    latency_rows: list[dict],
    top_rows: list[dict],
    *,
    days: int = DEFAULT_DAYS,
    phase_rows: list[dict] | None = None,
    intake_rows: list[dict] | None = None,
) -> str:
    """The four answers as text. No credential, no account id, no raw query."""
    lines = [f"{DATASET} — last {days} day(s)", ""]

    misses = miss_rows[0] if miss_rows else {}
    searches = _as_float(misses.get("searches")) or 0.0
    no_match = _as_float(misses.get("misses")) or 0.0
    rate = _as_float(misses.get("miss_rate"))
    lines.append("1. Miss rate (search)")
    if searches <= 0 or rate is None:
        lines.append("   no completed searches in the window")
    else:
        lines.append(
            f"   {rate * 100:.2f}%  ({_format_count(no_match)} misses / "
            f"{_format_count(searches)} searches)"
        )

    lines.extend(["", "2. p95 latency"])
    if not latency_rows:
        lines.append("   no completed tool calls in the window")
    else:
        for row in latency_rows:
            tool = str(row.get("tool") or "(unknown)")
            p95 = _as_float(row.get("p95_ms"))
            lines.append(f"   {tool:<22} {'n/a' if p95 is None else f'{p95:.0f} ms'}")

    lines.extend(["", "3. Where a search spends its milliseconds (p95 per phase)"])
    phase = (phase_rows or [{}])[0] if phase_rows else {}
    phased = _as_float(phase.get("phased_rows")) or 0.0
    if not phase_rows or not phased:
        lines.append("   no phase data yet — it is only written by searches after the 2026-11-15 deploy")
    else:
        lines.append(f"   {int(phased)} of {int(searches)} searches in the window carry phases")
        for key, label in (("lessons_p95", "corpus read (memo/KV/D1)"),
                           ("index_p95", "BM25 index (KV)"),
                           ("score_p95", "scoring"),
                           ("semantic_p95", "semantic fallback")):
            value = _as_float(phase.get(key))
            lines.append(f"   {label:<26} {'n/a' if value is None else f'{value:.0f} ms'}")

    lines.extend(["", "4. Top 10 hashed queries with no hits"])
    if not top_rows:
        lines.append("   no no-match searches in the window")
    else:
        for row in top_rows:
            query_hash = str(row.get("query_hash") or "")
            lines.append(f"   {query_hash:<16} {_format_count(row.get('misses'))} misses")

    lines.extend(["", "5. Intake coverage probe (was the corpus already answering it?)"])
    intake = intake_rows[0] if intake_rows else {}
    filed = _as_float(intake.get("filed")) or 0.0
    if filed <= 0:
        lines.append("   no intakes filed in the window")
    else:
        covered = _as_float(intake.get("covered")) or 0.0
        unmeasured = _as_float(intake.get("unmeasured")) or 0.0
        questions = _as_float(intake.get("questions")) or 0.0
        q_covered = _as_float(intake.get("questions_covered")) or 0.0
        measurable = filed - unmeasured
        share = (covered / measurable) if measurable > 0 else None
        lines.append(
            f"   filed {_format_count(filed)}; corpus already matched "
            + ("n/a (nothing measurable)" if share is None
               else f"{share * 100:.1f}% ({_format_count(covered)}/{_format_count(measurable)})")
        )
        lines.append(f"   not measurable (cold isolate): {_format_count(unmeasured)}")
        lines.append(
            "   questions: "
            f"{_format_count(questions)} filed, {_format_count(q_covered)} already matched"
        )

    return "\n".join(lines)


def main(argv: list[str] | None = None, environ: dict | None = None, opener=None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Read the misakanet_events Analytics Engine dataset "
            "(miss rate, p95, top misses)."
        ),
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_DAYS,
        help=f"window in days (1-{MAX_DAYS}, default {DEFAULT_DAYS})",
    )
    args = parser.parse_args(argv)
    env = os.environ if environ is None else environ
    token = str(env.get("CLOUDFLARE_API_TOKEN") or "").strip()
    account_id = str(env.get("CLOUDFLARE_ACCOUNT_ID") or "").strip()
    if not token:
        print("error: CLOUDFLARE_API_TOKEN is not set", file=sys.stderr)
        return 2
    if not account_id:
        print("error: CLOUDFLARE_ACCOUNT_ID is not set", file=sys.stderr)
        return 2
    try:
        _window(args.days)  # validate before the first request; the builders repeat the check
    except AnalyticsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    client = urllib.request.urlopen if opener is None else opener
    try:
        miss_rows = run_query(
            miss_rate_sql(args.days), account_id=account_id, token=token, opener=client
        )
        latency_rows = run_query(
            latency_sql(args.days), account_id=account_id, token=token, opener=client
        )
        top_rows = run_query(
            top_missed_sql(args.days), account_id=account_id, token=token, opener=client
        )
        phase_rows = run_query(
            phase_sql(args.days), account_id=account_id, token=token, opener=client
        )
        intake_rows = run_query(
            intake_coverage_sql(args.days), account_id=account_id, token=token, opener=client
        )
    except AnalyticsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(build_report(miss_rows, latency_rows, top_rows, days=args.days,
                   phase_rows=phase_rows, intake_rows=intake_rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
