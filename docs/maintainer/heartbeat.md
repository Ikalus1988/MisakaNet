# The daily heartbeat

One comment per UTC day on the long-lived issue labelled **`heartbeat`**, answering exactly three
questions: **who is calling, what they asked, and whether it helped.** The owner reads one
notification and does nothing — there is no vote, no button and no manual dispatch in the loop.
The point is the frame the project is built on: MisakaNet earns its keep as the owner's own
cross-agent failure memory, so the numbers that matter are calls, topics, and reuse.

| | |
|---|---|
| Composer | [`scripts/heartbeat_report.py`](../../scripts/heartbeat_report.py) |
| Sender | [`.github/workflows/heartbeat.yml`](../../.github/workflows/heartbeat.yml) |
| Schedule | `12 0 * * *` (00:12 UTC), plus `workflow_dispatch` for a re-run while testing |
| Comment | one per UTC day, on the issue labelled `heartbeat`; the marker `<!-- heartbeat-day:YYYY-MM-DD -->` is what makes a re-run **edit** that comment instead of posting a second one |
| Day reported | **the day that just ended.** A digest composed mid-day would be a partial count wearing the word "today", and would need a caveat on every number |

Running it by hand:

```bash
# the same thing the workflow does, against the live sources (needs the Cloudflare credential for D1)
python3 scripts/heartbeat_report.py --fetch --out /tmp/heartbeat.md

# a day already collected, or a fixture: no network, no credential
python3 scripts/heartbeat_report.py --day 2026-10-16 --counters-json rows.json \
  --analytics analytics.json --funnel funnel.json
```

## Panel 1 — who is calling

Reads `counters` rows with `scope='traffic'`, split into the four classes the worker classifies
every request into (`mcp`, `agent`, `crawler`, `pageview`) and the per-client buckets
`mcpclient:<name>`.

**The names are self-declared, and the panel says so in the comment itself.** A bucket is built
from MCP `initialize`'s `params.clientInfo.name` (or `.title`), falling back to the `User-Agent`,
lowercased, `[^a-z0-9._-]+` → `-`, trimmed to 32 characters and `unknown` when empty
(`workers/register-proxy-sw.js:6639`). So the panel answers *what name was claimed* — it is not an
identity, not a user count, and one agent with many names looks exactly like many agents sharing
one. `claude-code: 412` printed without that sentence would be a lie of emphasis, which is why a
test fails if the sentence is removed.

**Our own traffic is labelled and never counted as adoption.** `SELF_PRODUCED_NAMES` and
`SELF_PRODUCED_PREFIXES` in the composer are a reviewable parameter: the house prefix
`misakanet-` plus the bare names this repository's own tests and smoke paths declare. Those rows
are marked `self-produced (ours) — not adoption` and excluded from the **external, unclaimed**
number, which is the only number that could be evidence somebody outside called. A day whose named
calls are *all* ours says so in one sentence — that sentence is the single most valuable output
this digest has, because it is the one that stops an echo from reading as a pulse. Runtime names
(`node`, `curl-8.5.0`, `python-requests-2.31`, `unknown`) are labelled separately again: they are
external *and* unattributable, and calling them either "ours" or "callers" would be a guess.

## Panel 2 — what they asked

- **Top searches, rolling** — `/api/analytics`'s `top_searches`, which is `lesson_usage` rows with
  `event='search'` grouped by the query text. The window is whatever the endpoint uses (7 days at
  the time of writing), not the reported day, and the panel says so.
- **Generic strings are marked, not averaged in.** `top_searches` is a `GROUP BY` over whatever a
  caller sent, and the live top ten on 2026-10-16 carried `npm run build` (21 calls), `init` (12)
  and `start` (8) beside real topics. A count that blends them measures the blend. They stay
  visible with a `generic string — not a failure topic` note rather than being filtered out
  silently, because a hidden filter is the same dishonesty pointed the other way.
- **Declared intents** — `event='intent'` rows, usually empty. That is a reading of the store, not
  evidence that nobody had an intent, and the panel says which one it is.
- **Unanswered on the day** — `counters` rows with `scope='gap'`: searches that matched nothing
  (`workers/register-proxy-sw.js:3775`), with rows deleted once a lesson covers the query
  (`workers/register-proxy-sw.js:7028`). This is the demand the corpus failed to meet.
- **A prompt is not a query.** A `gap` bucket is `query.toLowerCase().trim()` with no length
  bound, which is exactly why `/api/analytics` withholds `knowledge_gaps` from anonymous callers
  (`workers/register-proxy-sw.js:7765`). This digest is a comment on a **public** issue, so only
  short, query-shaped text is repeated; anything newline-bearing, longer than 60 characters, or
  carrying a prompt marker renders as `<withheld: prompt-like text, not a query>`. Counts still
  include it — the miss is real even when the text is not printable. The full rows remain
  readable with the maintainer token.

## Panel 3 — whether it helped

**It is not measured, and the panel says that instead of implying otherwise.** `top_lessons` is
`lesson_usage` rows with `event='get_lesson'` — *how often a lesson was retrieved*. Fetched is not
fixed: nobody records whether the caller's problem went away. The panel prints retrieval counts,
states that no help number exists, and names the intended next step:

> **failure recurrence** — a normalized query that comes back on a later day is a signal the
> earlier answer did not stick.

That signal needs no identifier, no vote and no client change: the `gap` counter already stores
one row per normalized query per day, and `lesson_usage.query` carries the matched searches with
their `created_at`. It is **not implemented here**. The open item is a decision, not a blocker:
which series is authoritative (unanswered `gap` rows or matched searches), what normalization is
applied to compare two days, and what recurrence threshold is worth reporting. Until that lands,
the panel stays a retrieval count with the paragraph attached.

## Rule 4 — a day with no data says so

A source that could not be read and a source that was read and held nothing are two different
answers, and neither is `0`:

| state | how it renders |
|---|---|
| could not be read (`None`) | `⚠️ … could not be read for YYYY-MM-DD (reason). This is not a zero.` |
| read, empty (`[]`) | `… recorded no rows for that day` / `no traffic-class rows for …` |
| read, non-empty | the counts, with the day named |

The same rule is applied to the funnel: a day missing from `/api/funnel`'s window is reported as
absent, not as zero. The rule is the one `/api/funnel` already applies to its own `visit`
denominator ("a counter that cannot be read and a counter that is genuinely empty are two
answers", `workers/register-proxy-sw.js`), and the composer keeps the distinction at the source:
`traffic_class_counts(None, day) is None` but `traffic_class_counts([], day) == {}`.

## Sources, credentials, and what is deliberately not here

| source | what it is | its limit |
|---|---|---|
| `counters` (D1) | traffic classes, `mcpclient:` buckets, `gap` buckets | the client dimension exists only where a client sends `initialize`; `gap` text is caller-supplied |
| `GET /api/analytics` | rolling `lesson_usage` aggregates | `knowledge_gaps` and `mcpClients` are withheld there on purpose — read from D1 instead, without changing that policy |
| `GET /api/funnel` | `visit` / `register` / `authorize` / `pair` / `search` | `visit` counts only pageviews *this* worker serves (`/` and `/search/` come from `misakanet-web`); `register` counts **nodes**, and a client that omits `client_id` creates one per call, so it is neither people nor agents; `drop_off_rate` divides two different units and is deliberately unclamped, so the digest omits it and quotes its value rather than printing it as a rate |

- **No new endpoint, no change to what any counter records, no change to the withhold policy.**
  The composer is a reader.
- **`env.MCP_TOKEN` appears in no workflow.** The D1 read uses the Cloudflare credential the
  counters report already uses (`.github/workflows/d1-counters-report.yml`), and the job sits in
  the `automation` environment — reviewer-free, D1-scoped, and branch-restricted to `main`. The
  deploy-capable `release` credential is not used here: a cron behind a required reviewer does not
  become safer, it stops (`docs/maintainer/credentials-and-environments.md` §3).
- **A failed read does not fail the job.** The digest reports it in the comment and the step emits
  a `::warning::` annotation; turning it into a red run would give the owner a second notification
  that asks for an action, which is the thing a heartbeat must not do.
- **The four honesty rules are tested** in `tests/test_heartbeat_report.py`, each against a
  deliberately unprotected copy of the composer so the failure has been seen rather than assumed.
