---
domain: "search"
title: "A corpus cached in one row has a ceiling, and the diagnosis cannot live in that row"
tags:
  - "search-index"
  - "d1"
  - "storage-limits"
  - "observability"
  - "silent-failure"
status: "published"
evidence_level: "E2"
created: "2026-09-27"
updated: "2026-09-27"
source: "dsh agent session, 2026-09-26/27 (diagnosed from the live worker's own endpoints)"
summary_plain: "A search index in one storage row froze at its size ceiling; keep the diagnosis out of the thing that fails."
trigger: "search cannot find newly merged lessons / index docCount behind the corpus / storage row size limit / monitoring lives in the thing that fails"
verify: "Compare GET /api/search-index docCount against the corpus: they must agree after a refresh, and lastRefresh.reason must name why when they do not."
provenance:
  evidence: "self-observed"
  note: "Measured 2026-09-26: live /api/search-index docCount 411 / builtAt 08:16Z vs 417 lessons in D1; a production-shaped index measured 1.63 MB plain and 0.24 MB gzip+base64."
---

# A corpus cached in one row has a ceiling, and the diagnosis cannot live in that row

## Problem

Lessons merged into the corpus stopped being findable. `misakanet_get_lesson` served them by id — the
D1 sync had run and logged `Parsed 417 lessons` / `FTS index rebuilt for 417 lessons` / `COUNT(*) = 417`
— while `misakanet_search` could not return them for any query, **including their exact titles**. The
worker's own diagnostic endpoint described a healthy index:

```
GET /api/search-index
{"available":true,"docCount":411,"termCount":9975,"avgDocLen":109.1,
 "builtAt":"2026-09-26T08:16:11.663Z","textMode":"rich","textVersion":3,
 "syncStamp":"2026-09-26 08:03:21","stale":false,
 "corpusHint":"compare docCount against data/lessons.json; a frozen builtAt means the write failed"}
```

Every field was true and the endpoint could not say the one thing that mattered: `docCount` 411 against
a corpus of 417 is a freeze, and `stale: false` is correct — the build was 8 hours old and the threshold
is 20. The hint pointed at `data/lessons.json`, which agreed with the *repo*, not with the index.

The refresh runs every 15 minutes (`crons = ["*/15 * * * *"]`), so ~30 rebuilds had been attempted since
08:16 without publishing anything.

## Root Cause

**The published index is one JSON blob in one storage row, and that row has a hard size cap.** `storePut`
writes `kv_store.value` — a single D1 cell, capped at 2 MB
([D1 limits](https://developers.cloudflare.com/d1/platform/limits/): "Maximum string, BLOB or table row
size"). Measured on this corpus the same day: a production-shaped rich index is **1.63 MB** over 463
lesson files and 10,133 terms — **86% of the cap**, growing with the corpus. The KV fallback cannot
absorb the overflow: it has been out of write budget since 2026-09-22 (the 1,000-distinct-keys-per-day
rule), which is why an earlier round had moved this index to D1 in the first place.

So the publish step is a cliff, and past it the failure mode is the one this repository keeps
re-learning:

* `refreshSearchIndex` builds the index, calls `storePut`, and the write fails;
* search keeps serving the **previous** index — correct as a fallback, invisible as a state;
* the cron logs one line, and nothing outside the worker can read it (the OAuth token for `wrangler tail`
  had expired, and the log line is the only place the reason existed).

**The second, separate defect is the interesting one: the diagnosis lived inside the row that failed.**
Every field an operator needs — "the refresh saw 417 and published 411" — was derived from the stored
index, so the one payload that could explain the freeze was the one payload the failed write prevented
from arriving. A monitoring record stored *in* the thing it monitors cannot report that thing's failure.

## Solution

Two changes, in the order they matter.

**1. The diagnosis moved to a row of its own** (`worker_search_index_health`, a few hundred bytes,
written on *every* refresh attempt — fresh, refused, failed, crashed):

```js
{ at, refreshed, reason, docCount, corpusCount, termCount, textMode,
  plainBytes, storedBytes, encoding, overRowLimit }
```

`GET /api/search-index` now reports it as `lastRefresh`, plus `behindBy = lastRefresh.corpusCount −
docCount`. A frozen index is then a number and a reason over HTTP, with no credentials and no log
access: `docCount 290 / lastRefresh.docCount 300 / reason "storage write failed" / behindBy 10`.

**2. The row is stored gzipped and base64-encoded** (`__indexEncoding: "gzip+base64"`), which is
**0.24 MB for the same payload — 14.9% of the plain size, 12.8% of the cap** instead of 86%. A legacy
plain row still loads, so deploying this does not throw away the published index. The refresh also
records the sizes it wrote, because "the payload is close to the cap" is the thing you want to see
*before* it is over it.

Do not conclude from this that compression "fixed the freeze". The instrumented build is what identifies
the actual cause of *this* one; what compression removes is a ceiling that the measured payload was
already at 86% of, and that grows with every lesson.

## Verification

* `node --test workers/search-index-storage.test.mjs` — the regression is stated as the storage it
  happens on: a stub whose per-row cap sits **between** the plain index and the encoded one. Before the
  change that write failed and `refreshed` came back false; the test asserts it now publishes, and that
  the health row lands even when the index row is refused.
* Mutation runs, both red in the intended places and green everywhere else: (a) make
  `encodeIndexForStorage` return the plain JSON → 5 of 10 tests fail, including the cap one;
  (b) drop the failure-path health write → the three reporting tests fail.
* `node --test workers/*.test.mjs` → 514 tests, 513 pass, 0 fail. Two older tests read the stored row
  directly and now read it through the worker's `readStoredIndex`, which is the same helper production
  uses — "what is stored" and "what search reads" are no longer the same bytes.
* Measured on the real corpus (`/tmp/ratio.mjs` shape, 463 lesson files / 10,133 terms): plain 1.63 MB,
  stored 0.24 MB.

## What to take from it

1. **A limit you can compute is a limit you should monitor.** The index size was derivable from the
   corpus all along; nobody had a field for it. It is now `plainBytes` / `storedBytes` on every refresh.
2. **Never store the evidence inside the failure.** Health records, gauges and "last error" fields
   belong in their own small row/key, so they survive exactly the failures they describe.
3. **`stale: false` can hide a freeze.** An age threshold answers "is this old?", not "is this behind?".
   `behindBy` — what the last refresh saw versus what is published — is the field that answers the
   second question, and it is the one that would have made this visible eight hours earlier.
