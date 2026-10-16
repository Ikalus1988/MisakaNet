#!/usr/bin/env python3
"""The daily heartbeat: who is calling, what they asked, and whether it helped.

The project's purpose is to be the maintainer's own cross-agent failure memory, so the only
statistics that earn their keep are those three. This script composes them into one digest, and
`.github/workflows/heartbeat.yml` posts that digest as **one comment per UTC day** on the
`heartbeat` issue — the owner reads a notification and does nothing else.

Everything here that decides what a number *means* is a pure function over plain rows, so the
four honesty rules below are testable without a database, and the SQL/HTTP/`gh` plumbing is a thin
shell around them:

1. the client panel says its names are **self-declared** (`clientInfo.name`, or the User-Agent as
   a fallback) — it answers "what name was claimed", never "who this is";
2. our own probes, CI and monitors are a **reviewable list** here, labelled, excluded from the
   external count, and a day that is entirely ours says so in one sentence;
3. the "helped" panel prints **retrievals**, says out loud that "did this help" is not measured
   yet, and names failure recurrence as the intended next step;
4. a day with no rows says so — `None` (unreadable) and `[]` (genuinely empty) render as two
   different sentences and neither renders as `0`.

One more reading rides along, marked as *not* one of the three: the density of `E4`, the evidence
ladder's top rung, which the worker now confers on `COUNT(DISTINCT client_hint) >= 2`. It needs the
same D1 credential, and a real `0` there is a finding about the design rather than a quiet day.

Why D1 and not the public API for two of these: `/api/analytics` withholds `knowledge_gaps` and
`mcpClients` on purpose (a failed query can be a whole prompt; a client name is someone else's
tooling). This script reads them from `counters` with the same Cloudflare credential the counters
report already uses — it does not change the withhold policy, and it does not carry the
maintainer token (`env.MCP_TOKEN`) anywhere.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Mirrors of the worker's constants (`workers/register-proxy-sw.js`). Duplicated rather than
# imported: this script reads the *table*, and a rename on the worker side should show up here as
# "no rows for this day" instead of as a confidently wrong number. `workers/mcp-client-dimension.test.mjs`
# pins the worker's own spelling, and `tests/test_heartbeat_report.py` asserts these copies still
# match it — the mirror may be independent at run time, it may not be allowed to drift at review time.
MCP_CLIENT_BUCKET_PREFIX = "mcpclient:"
TRAFFIC_SCOPE = "traffic"
GAP_SCOPE = "gap"
TRAFFIC_TYPES = ("mcp", "agent", "crawler", "pageview")

#: `boundText()` bounds an analytics *display* string to this; a `gap` bucket is a normalized
#: query with no bound at all, which is why the redaction below is not decoration.
ANALYTICS_TEXT_LIMIT = 120

#: How much of an unanswered query this public comment will repeat. The full row is available to
#: the maintainer token; the comment is world-readable, so the bound is deliberately short.
GAP_TEXT_DISPLAY_LIMIT = 60

# ── The self/bot/monitor parameter (honesty rule 2) ──────────────────────────────────────────
#
# A digest that lets our own probes stand in for adoption is an echo, not a pulse. Every name
# below is *ours*, and this list is the parameter: adding to it is a review act, because a wrong
# entry converts somebody else's usage into "self-produced", which is the one error this panel
# exists to prevent.
#
# The `misakanet-` prefix is the house convention — `grep -rn "User-Agent" scripts/ packages/
# integrations/` finds `misakanet-install-smoke`, `misakanet-doctor`, `misakanet-setup`,
# `misakanet-cli`, `misakanet-site-activity` and friends — so a new probe is labelled without an
# edit here. The bare names were read off the repository's own call sites
# (`scripts/install_smoke.py`, `scripts/doctor.py`, `scripts/check_wheel_starts.py`,
# `scripts/cf_mcp_auth.py`, `tests/test_mcp_first_call_journey.py`,
# `workers/mcp-anonymous-read.test.mjs`, `packages/misakanet-setup/scripts/e2e-packaged-install.mjs`).
SELF_PRODUCED_PREFIXES = ("misakanet-",)
SELF_PRODUCED_NAMES = frozenset({
    "probe", "test", "journey-test", "health", "wheel-smoke", "mcp", "github-actions",
})

#: Names that identify a *runtime or HTTP client*, not a caller. `curl-8.5.0`, `node`,
#: `python-requests-2.31`: the worker's sanitiser lowercases and turns `[^a-z0-9._-]+` into `-`,
#: so the version arrives glued on with a dash. These are external and unattributable in both
#: directions — they could be a stranger or our own CI — and saying so is the honest reading.
RUNTIME_NAME_SHAPE = re.compile(
    r"^(?:node|node-fetch|node\.js|undici|curl|wget|python|python-requests|httpx|aiohttp|axios"
    r"|okhttp|java|go-http-client|wrangler|libwww-perl|postmanruntime|unknown|-)(?:[-/].*)?$"
)

# ── Generic strings that are not failure topics (rule 2's neighbour) ─────────────────────────
#
# `top_searches` is a `GROUP BY` over whatever text the caller sent. Measured live 2026-10-16, the
# top ten carried `npm run build` (21 calls), `init` (12) and `start` (8) beside real topics —
# averaging those in inflates "demand" with strings that name no problem. They are marked and kept
# visible, not filtered out: a silent filter would be the same dishonesty in the other direction.
GENERIC_QUERIES = frozenset({
    "init", "start", "stop", "run", "build", "install", "test", "help", "hi", "hello",
    "npm run", "npm run build", "npm install", "npm test", "npm start", "pip install",
})

#: The evidence ladder's top rung, as the worker defines it: a lesson retrieved by this many
#: *distinct* observed clients is `E4`. The worker's own constant is `E4_MIN_DISTINCT_CLIENTS`
#: (`workers/register-proxy-sw.js`, next to `countDistinctRetrievingClients`), and
#: `tests/test_heartbeat_report.py` fails if the two disagree — this mirror exists so the digest can
#: print the threshold it measured against, not so it can drift.
E4_MIN_DISTINCT_CLIENTS = 2

#: One row, four numbers. Held as a module constant so the test suite can run **this exact text**
#: against `sqlite3` and the worker's own `CREATE TABLE`, which is the only way to check the query's
#: selection semantics without production D1.
#:
#: `client_hint` is written only for a caller that sends a `client_id` / `X-MisakaNet-Client`, so the
#: fourth number under-counts by construction — a property, not a defect, and the panel says so.
E4_SQL = """SELECT
  (SELECT COUNT(*) FROM search_signals) AS rows_total,
  (SELECT COUNT(*) FROM search_signals WHERE solved = 1) AS rows_solved,
  (SELECT COUNT(DISTINCT top_id) FROM search_signals) AS lessons_seen,
  (SELECT COUNT(*) FROM (
     SELECT top_id FROM search_signals
      WHERE client_hint IS NOT NULL AND client_hint <> ''
      GROUP BY top_id
     HAVING COUNT(DISTINCT client_hint) >= {threshold}
   )) AS e4_lessons;""".replace("{threshold}", str(E4_MIN_DISTINCT_CLIENTS))

#: Substrings that make a failed query look like a prompt rather than a query. Together with the
#: length bound and a newline check this is what keeps a public comment from republishing the
#: text `/api/analytics` withholds. It is a heuristic and is described as one.
PROMPT_MARKERS = (
    "you are", "as an ai", "ignore previous", "ignore all previous", "system prompt",
    "assistant:", "please ", "i want you", "write me", "act as ", "your task",
)

DAY_MARKER = "<!-- heartbeat-day:{day} -->"
ISSUE_MARKER = "<!-- heartbeat-issue -->"

#: The reason strings are pasted into a **public** comment, so they are flattened to one short
#: line first: an unflattened `wrangler` error carries ANSI colour codes and newlines, which both
#: breaks the markdown table it lands in and buries the one sentence that matters.
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
REASON_LIMIT = 200


def reason_text(error: object) -> str:
    """One line, no escape codes, bounded — safe to paste into a public markdown table cell."""
    flat = " ".join(_ANSI.sub("", str(error)).split())
    return flat[:REASON_LIMIT]


# ── Pure composers ──────────────────────────────────────────────────────────────────────────

def day_marker(day: str) -> str:
    """The per-day token that makes a re-run edit today's comment instead of posting a second."""
    return DAY_MARKER.format(day=day)


def load_comments(text: str) -> list[dict]:
    """Comment objects from either a JSON array or JSON Lines.

    `gh api --paginate` concatenates one array per page, which is not one JSON document; the
    workflow asks `--jq '.[]'` for JSON Lines instead, and this reads both so a hand-saved file
    works too.
    """
    text = text.strip()
    if not text:
        return []
    try:
        document = json.loads(text)
    except json.JSONDecodeError:
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    if isinstance(document, dict):
        return [document]
    return list(document)


def find_comment_for_day(comments: list[dict], day: str) -> int | None:
    """The id of the comment already carrying `day`'s marker, or `None`.

    Idempotency lives here rather than in shell: the workflow pipes the issue's comments through
    this function, so "update instead of post twice" is the same rule the tests exercise.
    """
    marker = day_marker(day)
    for comment in comments:
        if marker in str(comment.get("body") or ""):
            return int(comment["id"])
    return None


def result_rows(payload: str) -> list[dict]:
    """Rows out of a `wrangler d1 execute --json` payload, or out of a bare row array.

    Wrangler answers with a list of result envelopes (`[{"results": [...], "success": true}]`); the
    fixtures in `tests/` and `--counters-json` pass the row array directly. An envelope that carries
    an `error` is skipped rather than turned into a row — a failed query must not become a row of
    zeroes at the call site that reads it.
    """
    document = json.loads(payload)
    if isinstance(document, dict):
        document = [document]
    rows: list[dict] = []
    for envelope in document:
        if not isinstance(envelope, dict):
            continue
        if isinstance(envelope.get("results"), list):
            rows.extend(envelope["results"])
        elif "error" not in envelope:
            rows.append(envelope)
    return rows


def _scope_rows(rows, scope: str, day: str) -> list[dict]:
    return [row for row in (rows or []) if row.get("scope") == scope and row.get("period") == day]


def traffic_class_counts(rows, day: str) -> dict[str, int] | None:
    """Today's counts for the four classes the worker classifies every request into.

    `None` means the rows could not be read; `{}` means they were read and held nothing. The two
    are different answers and the caller renders them differently (rule 4).
    """
    if rows is None:
        return None
    counts = {name: 0 for name in TRAFFIC_TYPES}
    seen = False
    for row in _scope_rows(rows, TRAFFIC_SCOPE, day):
        bucket = str(row.get("bucket") or "")
        if bucket in counts:
            counts[bucket] += int(row.get("count") or 0)
            seen = True
    return counts if seen else {}


def client_counts(rows, day: str) -> dict[str, int] | None:
    """Today's calls per self-declared client name, keys stripped of the `mcpclient:` prefix."""
    if rows is None:
        return None
    counts: dict[str, int] = {}
    for row in _scope_rows(rows, TRAFFIC_SCOPE, day):
        bucket = str(row.get("bucket") or "")
        if bucket.startswith(MCP_CLIENT_BUCKET_PREFIX):
            name = bucket[len(MCP_CLIENT_BUCKET_PREFIX):] or "unknown"
            counts[name] = counts.get(name, 0) + int(row.get("count") or 0)
    return counts if counts else {}


def gap_counts(rows, day: str) -> dict[str, int] | None:
    """Today's unanswered queries, keyed on the worker's normalized query text."""
    if rows is None:
        return None
    counts: dict[str, int] = {}
    for row in _scope_rows(rows, GAP_SCOPE, day):
        query = str(row.get("bucket") or "")
        counts[query] = counts.get(query, 0) + int(row.get("count") or 0)
    return counts if counts else {}


def e4_density(row: dict | None) -> dict | None:
    """The E4 count and its three denominators, from the single row `E4_SQL` returns.

    `None` in, `None` out: a failed read is not a density of zero, and the panel renders the two
    differently (rule 4) — which matters more here than anywhere else in the digest, because a real
    zero is a *finding* and a failed read is not.
    """
    if not row or "e4_lessons" not in row:
        return None
    return {
        "e4_lessons": int(row.get("e4_lessons") or 0),
        "lessons_seen": int(row.get("lessons_seen") or 0),
        "rows_total": int(row.get("rows_total") or 0),
        "rows_solved": int(row.get("rows_solved") or 0),
    }


def classify_client(name: str) -> str:
    """`self` (ours), `runtime` (a runtime name, not a caller), or `external`."""
    if name in SELF_PRODUCED_NAMES or name.startswith(SELF_PRODUCED_PREFIXES):
        return "self"
    if RUNTIME_NAME_SHAPE.match(name):
        return "runtime"
    return "external"


def client_label(name: str) -> str:
    """The sentence that stops a count from reading as an identity."""
    kind = classify_client(name)
    if kind == "self":
        return "self-produced (ours) — not adoption"
    if kind == "runtime":
        # `unknown` is the sanitiser's bucket for a client that named itself with nothing; a
        # runtime name is a client that named itself with its own runtime. Both are unattributable,
        # but only one of them is a name at all, and the label says which.
        if name in {"unknown", "-", ""}:
            return "external, unclaimed — the empty-name bucket"
        return "external, unclaimed — runtime name only, no identity claimed"
    return "external, unclaimed"


def split_clients(counts: dict[str, int]) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    """`(ours, external_and_unclaimed)`, each sorted by calls then name.

    The split is the point: only the second list can be evidence that somebody outside called.
    """
    ours, external = [], []
    for name, count in counts.items():
        (ours if classify_client(name) == "self" else external).append((name, count))
    order = lambda pair: (-pair[1], pair[0])  # noqa: E731 — a key, not a function anyone calls
    return sorted(ours, key=order), sorted(external, key=order)


def is_generic_query(query: str) -> bool:
    return query.strip().lower() in GENERIC_QUERIES


def looks_like_prompt(text: str) -> bool:
    """Is this failed *query* actually something else a caller sent?

    The `gap` bucket is `query.toLowerCase().trim()` with no length bound, and the public API
    withholds it for exactly this reason: a caller can send a whole prompt, and the counter keeps
    it. This comment is public too, so a prompt-shaped row is replaced rather than repeated.
    """
    lowered = text.lower()
    return (
        "\n" in text or "\r" in text
        or len(text) > GAP_TEXT_DISPLAY_LIMIT
        or any(marker in lowered for marker in PROMPT_MARKERS)
    )


def redact_gap_query(query: str) -> str:
    """A failed query as it may appear in a public comment: short, or marked as withheld."""
    if looks_like_prompt(query):
        return "<withheld: prompt-like text, not a query>"
    cleaned = "".join(char for char in query if char.isprintable()).strip()
    if len(cleaned) > GAP_TEXT_DISPLAY_LIMIT:
        return "<withheld: prompt-like text, not a query>"
    return cleaned or "<empty query>"


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return lines


def _sorted_top(counts: dict[str, int], limit: int) -> list[tuple[str, int]]:
    return sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))[:limit]


def pulse_line(analytics: dict | None, day: str, errors: dict[str, str]) -> list[str]:
    """The one-line trajectory: `lesson_usage` rows per UTC day, plus today's own count."""
    if analytics is None:
        return [f"**pulse** — ⚠️ `/api/analytics` could not be read for {day} "
                f"({errors.get('analytics', 'no reason recorded')}). This line is not a zero."]
    series = analytics.get("daily_requests") or []
    if not series:
        return [f"**pulse** — `/api/analytics` recorded no `lesson_usage` rows in its 7-day "
                f"window, so there is no trajectory to draw for {day}."]
    today = next((row for row in series if row.get("day") == day), None)
    history = " · ".join(str(row.get("count")) for row in series)
    if today is None:
        return [f"**pulse** — no `lesson_usage` row for {day} itself; the API's window reads "
                f"{history} rows per day, oldest first (a day with no row is not a day with zero "
                f"rows)."]
    return [f"**pulse** — {today.get('count')} `lesson_usage` rows on {day}; the API's rolling "
            f"window reads {history} rows per day, oldest first."]


def panel_who(counters, day: str, errors: dict[str, str]) -> list[str]:
    """Panel 1 — who is calling, with rule 1's sentence attached to the names."""
    lines = ["## 1 · Who is calling", ""]
    lines += [
        "> **These names are self-declared.** Each is `clientInfo.name` from the MCP `initialize`",
        "> handshake, or the `User-Agent` when a client sends none, lowercased and cut to 32",
        "> characters. It records **what a caller claimed**, never who it is: one agent with many",
        "> names and many agents sharing one name are identical here. It is not a user count.",
        "",
    ]

    classes = traffic_class_counts(counters, day)
    if classes is None:
        lines += [f"⚠️ **The traffic classes could not be read for {day}** "
                  f"({errors.get('counters', 'no reason recorded')}). This is not a zero — a "
                  f"counter that cannot be read and a counter that is genuinely empty are two "
                  f"different answers.", ""]
    elif not classes:
        lines += [f"The worker recorded no traffic-class rows for {day}. That is what an empty "
                  f"counter looks like, not a measurement of a quiet day.", ""]
    else:
        rendered = " · ".join(f"`{name} {classes.get(name, 0)}`" for name in TRAFFIC_TYPES)
        lines += [f"**calls on {day}** by traffic class: {rendered}", ""]

    counts = client_counts(counters, day)
    if counts is None:
        lines += [f"⚠️ **The self-declared client rows could not be read for {day}** "
                  f"({errors.get('counters', 'no reason recorded')}). Not a zero.", ""]
        return lines
    if not counts:
        lines += [f"No self-declared client rows were recorded for {day}. That is an empty store, "
                  f"not a statement that nobody called: only the `initialize` handshake writes "
                  f"one, so a client that skips it never enters this panel.", ""]
        return lines

    ours, external = split_clients(counts)
    named = sum(counts.values())
    lines += [f"**self-declared client names, {day}**", ""]
    shown = (ours + external)[:12]
    lines += _table(
        ["name (self-declared)", "calls", "what it is"],
        [[name, str(count), client_label(name)] for name, count in shown],
    )
    if len(counts) > len(shown):
        # Truncation is stated rather than silent: a table that stops at twelve without saying so
        # reads as the complete list.
        lines += ["", f"… {len(counts) - len(shown)} more self-declared names with fewer calls"]
    lines += ["", f"- named calls on {day}: **{named}**; only `initialize` carries a name, so this "
                  f"counts handshakes, not calls."]
    lines += [f"- **self-produced (ours): {sum(count for _, count in ours)}** — our own CI, probes "
              f"and monitors. Labelled, and never counted as adoption."]
    if external:
        external_total = sum(count for _, count in external)
        lines += [f"- **external, unclaimed: {external_total}** — a name that is not ours, so it "
                  f"counts calls by claimed name, not callers."]
    else:
        lines += ["- **every named call on this day was self-produced**: "
                  f"{named} of {named}. This day says nothing about adoption — the pulse here is "
                  "our own."]
    lines += [""]
    return lines


def panel_what(counters, analytics: dict | None, day: str, errors: dict[str, str]) -> list[str]:
    """Panel 2 — what they asked, and what the worker could not answer."""
    lines = ["## 2 · What they asked", ""]

    if analytics is None:
        lines += [f"⚠️ **`/api/analytics` could not be read for {day}** "
                  f"({errors.get('analytics', 'no reason recorded')}). Top searches and intents "
                  f"are missing, not zero.", ""]
    else:
        searches = analytics.get("top_searches") or []
        if searches:
            lines += ["**top searches — rolling 7 days** (`lesson_usage`, `event='search'`):", ""]
            lines += _table(
                ["query", "calls", "note"],
                [[str(row.get("query", "")), str(row.get("count", 0)),
                  "generic string — not a failure topic" if is_generic_query(
                      str(row.get("query", ""))) else ""]
                 for row in searches],
            )
            if any(is_generic_query(str(row.get("query", ""))) for row in searches):
                lines += ["", "_Generic strings are marked rather than averaged in: they are the "
                              "string `npm run build`, not a problem anyone hit, and a count that "
                              "mixes them with failure topics measures the mix._"]
        else:
            lines += [f"`/api/analytics` returned no search rows in its 7-day window for {day}."]
        lines += [""]

        intents = analytics.get("intents") or []
        if intents:
            lines += ["**declared intents — rolling 7 days**: " + " · ".join(
                f"`{row.get('intent')}` {row.get('count')}" for row in intents), ""]
        else:
            lines += ["**declared intents — rolling 7 days**: none recorded in the window. "
                      "(No intent rows is a reading of the store, not evidence that nobody had an "
                      "intent.)", ""]

    gaps = gap_counts(counters, day)
    if gaps is None:
        lines += [f"⚠️ **The unanswered-query rows could not be read for {day}** "
                  f"({errors.get('counters', 'no reason recorded')}). Not a zero.", ""]
        return lines
    if not gaps:
        lines += [f"**unanswered on {day}**: the `gap` counter recorded no rows for that day — no "
                  f"zero-result search was logged that day.", ""]
        return lines

    top = _sorted_top(gaps, 8)
    miss_total = sum(gaps.values())
    lines += [f"**unanswered on {day}** (`counters` scope `gap`: queries that matched nothing and "
              f"that no lesson covers): **{len(gaps)} distinct, {miss_total} misses**", ""]
    lines += [f"- `{redact_gap_query(query)}` ×{count}" for query, count in top]
    if len(gaps) > len(top):
        lines += [f"- … {len(gaps) - len(top)} more distinct queries"]
    lines += ["",
              "_A `gap` bucket is a normalized query with no length bound, so a caller can leave a "
              "whole prompt in it — which is why `/api/analytics` withholds this field and why only "
              "short query-shaped text is repeated here. Prompt-like rows are marked, not printed; "
              "the full rows are readable with the maintainer token._", ""]
    return lines


def panel_helped(analytics: dict | None, day: str, errors: dict[str, str]) -> list[str]:
    """Panel 3 — retrievals, and the plain statement that help is not measured yet."""
    lines = ["## 3 · Whether it helped", ""]
    lines += ["**This panel cannot answer that question yet, and it will not pretend otherwise.**",
              ""]
    if analytics is None:
        lines += [f"⚠️ **`/api/analytics` could not be read for {day}** "
                  f"({errors.get('analytics', 'no reason recorded')}), so even the retrieval "
                  f"counts are missing. Not a zero.", ""]
        return lines

    lessons = analytics.get("top_lessons") or []
    if lessons:
        lines += ["**top lessons — rolling 7 days** (`lesson_usage`, `event='get_lesson'`), i.e. "
                  "**how often a lesson was retrieved**:", ""]
        lines += _table(
            ["lesson", "retrievals (7d)"],
            [[str(row.get("lesson_id", "")), str(row.get("count", 0))] for row in lessons],
        )
        lines += [""]
    else:
        lines += ["`/api/analytics` returned no `get_lesson` rows in its 7-day window — no "
                  "retrieval was recorded, which is not the same as no lesson helping.", ""]

    lines += ["**Not measured: did this help?** A retrieval is a lesson that was *fetched*. "
              "Fetched is not fixed, and nothing here records whether the caller's problem went "
              "away — no vote, no follow-up, no identifier. There is no help number in this "
              "digest, only retrieval counts.", "",
              "The intended next step is **failure recurrence**: a normalized query that comes "
              "back on a later day is a signal the earlier answer did not stick. It is observable "
              "without any identifier — the `gap` counter already stores one row per normalized "
              "query per day, and `lesson_usage.query` carries the matched searches with their "
              "`created_at` — so it needs no worker change and no client change. It is not "
              "implemented here: choosing which series is authoritative (unanswered `gap` rows or "
              "matched searches), the normalization, and the threshold are the open item. Until "
              "it lands, this panel is a retrieval count with this paragraph attached.", ""]
    return lines


def panel_e4(e4: dict | None, day: str, errors: dict[str, str]) -> list[str]:
    """A separate reading: how many lessons actually reach the ladder's top rung.

    Deliberately **not** folded into the three panels. "Who is calling" is about this day's traffic
    and "whether it helped" is about retrievals; E4 is a cumulative property of the whole
    `search_signals` table, and mixing a stock into a day's flow is how a digest starts lying by
    adjacency.
    """
    lines = [
        "---",
        "",
        "## A separate reading · how dense the E4 rung is",
        "",
        "_Not one of the three questions above._ `E4` is the top rung of the evidence ladder: a "
        f"lesson retrieved by **{E4_MIN_DISTINCT_CLIENTS} distinct clients** "
        f"(`COUNT(DISTINCT client_hint) >= {E4_MIN_DISTINCT_CLIENTS}`, the worker's "
        "`E4_MIN_DISTINCT_CLIENTS`) — conferred by an observation, and impossible to type into a "
        "lesson. Nobody had measured it against the real table, and this digest is the one job "
        "here with the credential to do it.",
        "",
    ]
    if e4 is None:
        lines += [f"⚠️ **The E4 count could not be read for {day}** "
                  f"({errors.get('search_signals', 'no reason recorded')}). That is **not** a density "
                  f"of zero: a zero here would be a finding about the design, and a failed read is a "
                  f"failed read.", ""]
        return lines

    lines += [f"**E4 lessons: {e4['e4_lessons']} of {e4['lessons_seen']}.** `search_signals` holds "
              f"{e4['rows_total']} rows, {e4['rows_solved']} of them hits (`solved=1`).", ""]
    if e4["e4_lessons"] == 0:
        lines += [
            "**Read the 0 as a finding, not as a fault.** No lesson has been retrieved by "
            f"{E4_MIN_DISTINCT_CLIENTS} distinct clients, so the top rung is empty — and that is "
            "evidence about the design, not a broken counter to be nursed back to health with "
            "softer wording. The rung is conferred only by "
            f"{E4_MIN_DISTINCT_CLIENTS} distinct `client_hint` values, and `client_hint` is written "
            "only for a caller that sends a `client_id`; an anonymous caller leaves none. So this "
            "number under-counts by construction, and under-counting is the direction a trust "
            "signal is allowed to be wrong in: silence can make it too small, but no lesson body "
            "and no vote button can make it too big.", "",
        ]
    else:
        lines += [f"{e4['e4_lessons']} lesson(s) have been retrieved by at least "
                  f"{E4_MIN_DISTINCT_CLIENTS} distinct clients. The same construction note applies: "
                  f"anonymous callers carry no `client_hint`, so this is a floor, never a ceiling.", ""]
    return lines


def panel_sources(counters, analytics: dict | None, funnel: dict | None, e4: dict | None,
                  day: str, errors: dict[str, str]) -> list[str]:
    """The footer: what was read, what each number cannot say, and the errors, if any."""
    lines = ["---", "", "## Sources, and what each number cannot say", ""]
    counters_state = ("read" if counters is not None
                      else f"**could not be read** ({errors.get('counters', 'no reason recorded')})")
    analytics_state = ("read" if analytics is not None
                       else f"**could not be read** ({errors.get('analytics', 'no reason recorded')})")
    funnel_state = ("read" if funnel is not None
                    else f"**could not be read** ({errors.get('funnel', 'no reason recorded')})")
    e4_state = ("read" if e4 is not None
                else f"**could not be read** ({errors.get('search_signals', 'no reason recorded')})")
    lines += _table(
        ["source", "state", "what it is"],
        [
            ["`counters` (D1)", counters_state,
             "the worker's own rows: traffic classes, self-declared client names, unanswered "
             "queries"],
            ["`/api/analytics`", analytics_state,
             "rolling 7 days of `lesson_usage`; its `knowledge_gaps` and `mcpClients` are withheld "
             "there and read from D1 here instead"],
            ["`/api/funnel`", funnel_state, "the first-call funnel, from the worker's counters"],
            ["`search_signals` (D1)", e4_state,
             "the E4 reading above: rows, hits, distinct lessons, and how many lessons sit at the "
             "top rung"],
        ],
    )
    lines += [""]

    if funnel is None:
        lines += [f"The funnel could not be read for {day}"
                  f" ({errors.get('funnel', 'no reason recorded')}) — no register/search numbers "
                  f"this run.", ""]
    else:
        today = next((row for row in (funnel.get("series") or []) if row.get("date") == day), None)
        if today is None:
            lines += [f"The funnel reported no row for {day} in its window, so there is no "
                      f"register/search count for that day (absent is not zero).", ""]
        else:
            lines += [
                f"Funnel on {day}: register {today.get('register')} · search {today.get('search')} · "
                f"visit {today.get('visit')}. Read it carefully: `visit` counts only the pageviews "
                f"*this* worker serves (`/` and `/search/` are served by `misakanet-web` and never "
                f"reach it), and `register` counts **nodes** — a client that omits `client_id` "
                f"creates a fresh one on every call — so it is neither people nor agents.", "",
            ]

    # `drop_off_rate` is a ratio between two different units and is deliberately unclamped, so it
    # can be negative; printed in a list of counts it would read like a rate, which it is not. The
    # live value is quoted instead of defined away, because on a register-heavy day it *is* the
    # honest reading of "the funnel is measuring unlike things".
    rate = None
    if funnel is not None:
        today = next((row for row in (funnel.get("series") or []) if row.get("date") == day), None)
        if today is not None:
            rate = today.get("drop_off_rate")
    lines += ["`drop_off_rate` is omitted on purpose: it divides `register + pair` by `visit`, two "
              "different units, and is deliberately unclamped"
              + (f" — the value for {day} was `{rate}`" if rate is not None else "")
              + ". Printed as a rate it would read like one.", ""]

    lines += ["Generated by `scripts/heartbeat_report.py`; one comment per UTC day, edited in "
              "place on re-run. It carries no maintainer token and changes no counter — it is a "
              "reading of what the worker already recorded.", ""]
    return lines


def render_digest(*, day: str, counters, analytics: dict | None, funnel: dict | None,
                  e4: dict | None = None, errors: dict[str, str] | None = None) -> str:
    """The whole comment body for one UTC day.

    `counters` / `analytics` / `funnel` / `e4` are plain data or `None` for "could not be read";
    `errors` maps a source to the reason, so the digest can say what it could not see instead of
    printing a number nobody can trust.
    """
    errors = errors or {}
    lines = [
        day_marker(day),
        ISSUE_MARKER,
        "",
        f"# 💓 MisakaNet daily heartbeat — {day}",
        "",
        "_One comment per UTC day, covering the day that just ended: a count reported while its day "
        "is still running is a partial count, and a heartbeat that quotes partial counts needs a "
        "caveat on every number. Re-running the workflow edits **this** comment rather than "
        "posting a second one. It answers three questions — who is calling, what they asked, "
        "whether it helped — and it needs nothing from anyone. The caveats at the bottom are part "
        "of the numbers, not small print._",
    ]
    lines += [""] + pulse_line(analytics, day, errors) + ["", "---", ""]

    if counters is None and analytics is None and funnel is None:
        lines += [f"**No source could be read for {day}** — every panel below is a report of a "
                  f"failed read, not of a quiet day.", ""]

    lines += panel_who(counters, day, errors)
    lines += ["---", ""]
    lines += panel_what(counters, analytics, day, errors)
    lines += ["---", ""]
    lines += panel_helped(analytics, day, errors)
    lines += panel_e4(e4, day, errors)
    lines += panel_sources(counters, analytics, funnel, e4, day, errors)
    return "\n".join(lines).rstrip() + "\n"


# ── Thin plumbing (the only part that needs a network or a credential) ───────────────────────

def wrangler_failure(stdout: str, stderr: str) -> str:
    """The one useful sentence out of a failed `wrangler d1 execute`.

    With `--json` the real message is a JSON `error.text` on stdout (the auth failure that a
    runner without the credential sees, for instance) and stderr holds colour codes, proxy
    warnings and a Node deprecation notice. Prefer the former; flatten either way.
    """
    try:
        document = json.loads(stdout)
        if isinstance(document, dict) and isinstance(document.get("error"), dict):
            text = document["error"].get("text")
            if text:
                return reason_text(text)
    except json.JSONDecodeError:
        pass
    return reason_text(stderr or stdout or "wrangler failed with no output")


def fetch_counter_rows(day: str) -> list[dict]:
    """Every `counters` row for one day, with the credential the counters report already uses.

    One query rather than three: `traffic` and `gap` are the only scopes this digest reads, and a
    single statement keeps the failure mode simple (either the day's rows arrive or they do not).
    """
    sql = ("SELECT scope, bucket, period, count FROM counters "
           f"WHERE period = '{day}' AND scope IN ('{TRAFFIC_SCOPE}', '{GAP_SCOPE}');")
    result = subprocess.run(
        ["wrangler", "d1", "execute", "misakanet-db", "--remote", "--json", "--command", sql],
        cwd=REPO_ROOT / "workers", capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(wrangler_failure(result.stdout, result.stderr))
    return result_rows(result.stdout)


def fetch_e4_density() -> dict | None:
    """Run `E4_SQL` against D1, through the same credential and the same `wrangler` invocation.

    `None` when the table does not exist yet (the worker creates it lazily, so a young deployment
    answers `no such table`) rather than raising: the digest already has a sentence for "could not be
    read", and it is a truer one than a traceback.
    """
    result = subprocess.run(
        ["wrangler", "d1", "execute", "misakanet-db", "--remote", "--json", "--command", E4_SQL],
        cwd=REPO_ROOT / "workers", capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(wrangler_failure(result.stdout, result.stderr))
    rows = result_rows(result.stdout)
    return e4_density(rows[0] if rows else None)


def fetch_json(url: str) -> dict:
    """A public GET. `urllib` rather than a client library: this repository's Python side has zero
    runtime dependencies by design, and both endpoints are plain JSON."""
    request = urllib.request.Request(url, headers={"User-Agent": "misakanet-heartbeat/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 — fixed https URLs
        return json.loads(response.read().decode("utf-8"))


def collect(day: str) -> tuple[list[dict] | None, dict | None, dict | None, dict | None,
                               dict[str, str]]:
    """Read every source, keeping each failure as a *reason* rather than as a zero."""
    errors: dict[str, str] = {}
    try:
        counters: list[dict] | None = fetch_counter_rows(day)
    except Exception as error:  # noqa: BLE001 — the digest reports the reason, it does not crash
        counters, errors["counters"] = None, reason_text(f"{type(error).__name__}: {error}")
    try:
        e4: dict | None = fetch_e4_density()
    except Exception as error:  # noqa: BLE001 — same reason: a failed read is reported, not fatal
        e4, errors["search_signals"] = None, reason_text(f"{type(error).__name__}: {error}")
    try:
        analytics: dict | None = fetch_json("https://misakanet.org/api/analytics")
    except (urllib.error.URLError, OSError, ValueError) as error:
        analytics, errors["analytics"] = None, reason_text(f"{type(error).__name__}: {error}")
    try:
        funnel: dict | None = fetch_json("https://misakanet.org/api/funnel?days=7")
    except (urllib.error.URLError, OSError, ValueError) as error:
        funnel, errors["funnel"] = None, reason_text(f"{type(error).__name__}: {error}")
    return counters, analytics, funnel, e4, errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--day", help="UTC day to report, YYYY-MM-DD (default: today UTC)")
    parser.add_argument("--counters-json", type=Path,
                       help="a saved `wrangler d1 execute --json` output, or a bare row array")
    parser.add_argument("--analytics", type=Path, help="a saved /api/analytics payload")
    parser.add_argument("--funnel", type=Path, help="a saved /api/funnel payload")
    parser.add_argument("--e4-json", type=Path,
                       help="a saved `E4_SQL` result (one row), or nothing to leave it unread")
    parser.add_argument("--fetch", action="store_true",
                       help="read all three sources live (needs the Cloudflare credential for D1)")
    parser.add_argument("--out", type=Path, help="write the digest here instead of stdout")
    parser.add_argument("--find-comment", metavar="DAY",
                       help="print the id of the comment already carrying DAY's marker, else nothing")
    parser.add_argument("--comments-json", type=Path,
                       help="comments to search (default: stdin); JSON array or JSON Lines")
    args = parser.parse_args(argv)

    if args.find_comment:
        text = args.comments_json.read_text(encoding="utf-8") if args.comments_json else sys.stdin.read()
        found = find_comment_for_day(load_comments(text), args.find_comment)
        print("" if found is None else found)
        return 0

    day = args.day or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    counters: list[dict] | None = None
    analytics: dict | None = None
    funnel: dict | None = None
    e4: dict | None = None
    errors: dict[str, str] = {}

    if args.fetch:
        counters, analytics, funnel, e4, errors = collect(day)
    if args.counters_json:
        counters = result_rows(args.counters_json.read_text(encoding="utf-8"))
    if args.analytics:
        analytics = json.loads(args.analytics.read_text(encoding="utf-8"))
    if args.funnel:
        funnel = json.loads(args.funnel.read_text(encoding="utf-8"))
    if args.e4_json:
        rows = result_rows(args.e4_json.read_text(encoding="utf-8"))
        e4 = e4_density(rows[0] if rows else None)

    digest = render_digest(day=day, counters=counters, analytics=analytics, funnel=funnel, e4=e4,
                           errors=errors)
    if args.out:
        args.out.write_text(digest, encoding="utf-8")
    else:
        sys.stdout.write(digest)
    for source, reason in errors.items():
        print(f"::warning::{source} could not be read: {reason}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
