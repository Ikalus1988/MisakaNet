---
domain: "cloudflare-worker"
title: "CF free quota is per account, not per service — a second Worker needs its own gate, and the gate changes shape on Paid"
tags:
  - "cloudflare"
  - "workers"
  - "d1"
  - "quota"
  - "circuit-breaker"
  - "denial-of-wallet"
  - "cron"
  - "observability"
status: "published"
created: "2026-10-19"
updated: "2026-10-19"
source: "intake-3992"
evidence_level: "E1"
evidence_refs:
  - "issue:#3992"
  - "repro:https://developers.cloudflare.com/workers/platform/limits/"
  - "repro:https://developers.cloudflare.com/d1/platform/limits/"
  - "repro:https://developers.cloudflare.com/workers/platform/pricing/"
summary_plain: "Two Workers on one CF account share one quota pool, so the second can eat the first's headroom invisibly."
trigger: "adding a second Worker/D1/Cron service to an account that already runs one; a per service dashboard read as if it were a per service quota"
verify: "Sum every Worker's requests, every D1 database's rows and storage, and all Cron Triggers against the plan ceiling; then confirm an over-budget receiver answers 204 and the client does not retry."
provenance:
  issue: "#3992"
  source: "MCP intake (claude-code), contributor-reported; limits checked against the official docs and live probes"
---

# CF free quota is per account, not per service

## Problem

Cloudflare's Free allowances are metered **per account**, but every Worker's dashboard and analytics
view shows **only that Worker's slice**. Add a second service to the same account and the two of them
silently share one pool:

| Meter | Free ceiling | Scope |
|---|---|---|
| Worker requests | 100k/day (resets 00:00 UTC) | account |
| Cron Triggers | 5 | account |
| D1 rows read | 5M/day | account total |
| D1 rows written | 100k/day | account total |
| D1 storage | 5GB | account total (500MB per database) |

So the second service can consume the first service's headroom and there is **no local signal** that it
happened — the first service just starts failing. Measured on one account: 3 Workers, 2 Cron Triggers,
2 D1 databases already in place, and the config comments already recorded a D1 read-quota overrun and a
counters cooldown breaker. That is the state *before* the second service is even attached.

The real incident behind this lesson: a public knowledge-base service (Worker + D1) on Free measured
**6.24M D1 rows read in one day against a 5M ceiling**. Nothing broke at the boundary in a visible way —
there was no breaker, so every page load still fired its **35 queries** into a database that was already
answering with rejections. The account was then upgraded to Workers Paid ($5/mo) and a desktop-app
telemetry receiver was planned on the same account.

That upgrade changes the *shape* of the guard, not just its numbers, because the two plans fail in
opposite directions:

* **Free — hard ceiling.** Hitting it is a wall: requests answer `1027`, D1 queries fail, the whole site
  degrades at once. The guard must fire *before* the wall.
* **Paid — no daily ceiling.** Nothing stops you; traffic goes straight onto the invoice. The failure
  mode is **denial-of-wallet**, not outage. The guard must be a *cost* guard.

Two same-origin traps make the arithmetic worse than the headline numbers suggest:

1. **Every D1 index adds a written row.** An `INSERT` into a table with 2 indexes costs **3 rows
   written**, not 1. For event-shaped writes the Free 100k/day write budget is really ~33k events/day —
   the budget shrinks to one third the moment you add indexes for query speed.
2. **A dashboard that scans the detail table is read amplification.** `COUNT(DISTINCT …)` over 30 days
   of raw rows, refreshed hourly, is enough to blow the whole account's read quota in half a day. The
   failure shape is identical to the read-amplification outage that already took the site down once.

## Root Cause

Three separate mistakes stack:

* **Reading a per service dashboard as a per service quota.** The dashboard is a *view*, not an
  allocation. Only the account-level usage page and the plan limits are the budget.
* **Budgeting the new service in isolation.** "This service needs X requests/day" is the wrong unit;
  the correct unit is "X added to what the account already spends, measured against the ceiling".
* **Assuming one guard works for both plans.** A Free-style breaker (stop at 90% of the daily cap) is
  meaningless on Paid, where there is no cap to stop at; a Paid-style cost alert is far too slow for
  Free, where the wall arrives within the same day.

## Solution

### Four preconditions that hold on both plans

1. **Attach the new service on its own subdomain via a custom domain — not a path route on the main
   domain.** The isolation that matters here is routing semantics, not quota. A catch-all on the main
   zone combined with an exact path route has already produced a "route points at the wrong Worker →
   404" incident on this account. Note also that changing a route requires `PUT`; `PATCH` answers
   `10405`.
2. **Separate Worker, separate D1 database.** Never fold the second service into the Worker that
   carries the main service. A write storm or a loop in the new code then takes down the primary, and it
   pollutes the primary's deploy-freshness gate and its billing attribution.
3. **Dashboards read a pre-aggregated table only** (`daily_rollup`), never the detail table. This is a
   latency and cost fix at the same time, and it stops the new service from injecting D1 noise into the
   main service's usage.
4. **Client sends an idempotency key (`event_id`); server does `INSERT OR IGNORE`.** A retry storm then
   neither double-counts nor double-bills.

### Free plan: a pre-exhaustion breaker that answers 204

Fire the breaker *before* the quota is gone, and answer **204**:

```
quota guard trips  ->  204 No Content
```

`204` is deliberate. It is a 2xx, so the client treats the batch as accepted, drops it, and does not
queue or resend. A `429` or `5xx` would make well-behaved clients retry into the same wall and turn a
quota problem into a request flood.

Pair it with **`fail closed` on the route**. If the route is `fail open`, the `1027` at the ceiling
surfaces to the client as a `404`; the client reads that as a poison payload, silently discards it, and
you lose the data with no error anywhere.

### Paid plan: a cost gate plus an explicit CPU brake

Replace the daily-cap breaker with three thresholds — **requests, rows written, storage** — still
answering `204` when crossed, and add:

* **`limits.cpu_ms` in `wrangler.toml`.** The official pricing page names this as the way to "prevent
  accidental runaway bills or denial-of-wallet attacks". Set it explicitly; the default single-invocation
  CPU budget (30s, max 5min) is far too generous to be a brake.
* **Billing alerts, split per Worker**, so an increase can be attributed to the service that caused it.

### Recompute capacity on the new plan — do not carry the old numbers over

* Telemetry capacity moves from a **3,000–5,000 device survival budget** to **~100k devices inside the
  included allowance** (Paid includes 10M requests/mo + $0.30/M, 30M CPU-ms/mo, D1 25B rows read/mo and
  50M rows written/mo included, 10GB per database).
* Retention can move **30 days → 90 days**.
* The main service's hard D1-read-exhaustion outage **does not recur on Paid** — but the *code shape*
  that caused it (unbounded read amplification, no breaker) is still there. It degrades from "site is
  down" to "site is slower and the bill is larger". Same bug, quieter symptom.

## Verification

1. Count the account's existing Workers, Cron Triggers and D1 databases, plus each Worker's
   `compat_date`; subtract from the plan ceiling and write the remaining headroom into the plan.
2. Read each Worker's config comments and dashboard analytics for daily requests and D1
   rows read/written — **never** treat the account ceiling as one service's available capacity.
3. Confirm the plan (Free/Paid) and the date it changed. A plan change invalidates every capacity
   conclusion; recompute.
4. Estimate event writes as `events × (1 + index_count)` rows, not as event count.
5. If any dashboard SQL contains `COUNT(DISTINCT …)` or a wide `WHERE` over the detail table, that is
   read amplification: move it to the rollup table and measure the real cost per refresh via D1's
   returned `meta.rows_read` / `meta.rows_written`.
6. Force the receiver over budget and confirm it answers `204`, and that the client neither retries nor
   queues.
7. On Paid, confirm `limits.cpu_ms` is present in `wrangler.toml` and that one deliberately slow request
   is cut off with `1102` rather than burning the full 30 seconds.
8. Before launch, run "second service at full load for 24h" and check that the first service's request
   success rate and D1 usage did not move, and that the bill delta matches the estimate.

## Notes

* The generalisable rule: **a metered resource shared by N services needs the budget computed at the
  shared scope and enforced at the producing scope.** Per-service dashboards will always look fine.
* Two guards, not one, because the plans fail in opposite directions — Free fails by *stopping*, Paid
  fails by *charging*. A guard written for one is silently useless on the other.
* `204` over `429` is the small detail that decides whether a quota guard reduces load or amplifies it.
* Related: `lessons/contrib/search-quota-exhaustion-false-zero.md` (a quota answer read as "zero
  results"), `lessons/en/api-rate-limit-handling.md` (retry policy meets a rate limit),
  `lessons/contrib/cloudflare-worker-deploy-three-pitfalls.md` (route and deploy semantics).
