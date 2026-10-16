## First-Call Funnel Tracking

### Goal
Measure and optimize the first-time user journey: discovery -> registration -> first search.

### Metrics
Five day-level integer counts, written by the worker itself into the `counters` store under
`scope='funnel'` (one row per event per UTC day), plus two ratios derived from them at read time.
No cookie, no IP, no `client_id`, no per-query bucket: the storage shape has no field a person could
be recognised by, and that is a property of the shape rather than of a policy.

- `funnel.visit` — requests this worker served that `classifyRequest` put in the `pageview` class.
  It is **not** "unique visitors", and cannot be: a unique visitor is a per-person fact and no
  identifier is kept. It also only sees what reaches this worker — the site's home page and
  `/search/` are served by `misakanet-web` from `docs/`, so the population here is roughly `/start`
  (plus `/connect`, which 301s to it). Read it as "entry requests (worker-visible)", never as a headcount.
- `funnel.register` — `misakanet_register` calls that minted a **new node**. A `client_id` renewal is
  not one, and neither is a call whose token could not be stored (the caller is asked to retry).
- `funnel.search` — `misakanet_search` calls the worker **answered** that day. A hit and a no-match
  both count once; a burst-refused call counts zero.
- `funnel.authorize` / `funnel.pair` — the two steps of the **human** door: a pairing code issued by
  `POST /mcp/connect`, and that code exchanged for a token by `POST /mcp/pair`. Somebody who arrives
  from `/start` never calls `misakanet_register`, so without these two the funnel would read every
  human visitor as a drop-off.
- `funnel.first_search` — **retired**, and not approximated. "First" relates one search to the caller
  who made it, which needs a cross-session identifier; the client half's contract is "no credential,
  no account, no client_id" (`docs/maintainer/client-half-acceptance.md`, D3). Use `funnel.search`
  and the derived `activation_per_register` ratio below.
- `funnel.drop_off` — **not stored; derived at read time** from the day's aggregates as
  `1 - (register + pair) / visit`. A per-visitor drop-off would have to connect a visit to a
  registration, which is the join this design refuses to make. It is a coarse proxy — the numerator
  counts nodes and pairs, the denominator counts requests, and it can go negative when more nodes
  registered than pages were served — so read the trend, never the level.
- `funnel.error_search` — searches whose result set was empty. Already implemented, and unchanged:
  `lesson_usage.event='no_match'`, `search_signals.solved=0`, and `GET /api/insights/unsolved-map`.

### Implementation
1. Write: `workers/register-proxy-sw.js` — `bumpCounter(env, "funnel", <event>, <UTC day>, 1)`. `visit`
   rides the existing batched traffic flush (it is the same pageview count); the other four are
   one counter upsert each. `workers/funnel-events.test.mjs` pins every trigger and the paths that
   must not count.
2. Read: `GET /api/funnel?days=N` (clamped 2–30, default 7) — the per-day counts plus
   `activation_per_register` and `drop_off_rate`. The body is identical for every caller, so it is
   served with a shared 300s TTL; a day with no rows reports zeros/nulls rather than disappearing.
3. Storage: `counters` rows (`scope='funnel'`, `period=<UTC day>`), D1 first with the
   `counters:funnel:<event>:<day>` KV key as the fallback — no schema change, no new table.
4. Gate: `tests/test_funnel_event_names.py` — the event set is closed, no write argument may come
   from the request, neither the retired nor the derived name may appear as a bucket, and this file
   must keep naming the same five events.

### Success Criteria
- <5min time-to-first-search
- <20% drop-off at registration
- >80% first-search success rate

The first two are stated as individual journeys and the data is five day-level counts, so they are not
computable as written. Watch the trend of `drop_off_rate` and `activation_per_register` from
`GET /api/funnel` instead, and treat a threshold as a prompt to look rather than as a pass/fail.
