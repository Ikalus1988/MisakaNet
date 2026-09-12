---
title: 'Two truncations silently became the soul of an agent-facing search: a default page size and a 400-char projection'
domain: backend
tags:
  - search
  - bm25
  - retrieval
  - sql
  - pagination
  - agent-tooling
  - observability
  - verification
status: published
created: '2026-09-12'
updated: '2026-09-12'
source: misakanet-search-corpus-truncation-2026-09-12
evidence_level: E2

provenance:
  source: "external"
  contributor: "Ikalus1988"
  merged_at: "2026-09-12"
  evidence: "post-publication"
---

# Two truncations silently became the soul of an agent-facing search: a default page size and a 400-char projection

## Problem

An MCP tool served `misakanet_search` over a corpus of 384 failure lessons. Agents reported that
queries which *should* have hit returned either nothing or unrelated lessons, while the same queries
run locally over the repository's own JSON snapshot matched correctly. Same corpus, same query, two
different answers — one process, the deployed worker, was demonstrably reading a smaller or poorer
view of the data than the other.

The worker maintained its own BM25 index in KV and reported its size at `GET /api/search-index`:

```json
{"available": true, "docCount": 100, "termCount": 1470, "avgDocLen": 25.2}
```

`docCount: 100` against a 384-lesson corpus. Two independent truncations were stacked, and both were
invisible from the outside because each one returned *valid-looking* results.

## Root Cause

**Truncation 1 — a default page size became the corpus.** The single internal loader looked like
this:

```js
async function fetchLessonsFromD1(env, filters = {}) {
  const limit = Math.min(Math.max(parseInt(filters.limit, 10) || 100, 1), 5000);
  const sql = `SELECT id, title, ... FROM lessons` + where +
              ` ORDER BY updated DESC LIMIT ${limit}`;
  ...
}
```

That `|| 100` is a reasonable *paging* default for the public HTTP endpoint, where callers pass
`?limit=`. But the internal search path called it with no filters at all:

```js
const fromD1 = await getWithCache(env, "proxy:lessons:d1", () => fetchLessonsFromD1(env));
```

so `parseInt(undefined, 10) || 100` evaluated to 100, and every consumer of the loaded list — the
naive matcher *and* the cron-built BM25 index — silently worked off the 100 most recently updated
lessons. Nothing errored: a search over 26% of the corpus returns full, well-formed results, and
`ORDER BY updated DESC` means the missing 284 lessons are exactly the older ones, which no one
notices until they need one of them.

**Truncation 2 — a display cap became the recall ceiling.** The same function projected the row:

```js
description: (r.summary || r.problem || "").slice(0, 400)
```

`summary` is non-empty for almost every lesson, so the `||` short-circuited and the *problem /
root_cause / solution* body was never selected at all. The index therefore contained titles and
one-sentence summaries: a lesson whose body says `Exit code 137 (128 + SIGKILL 9)` was unfindable
for `exit code 137`. The database *had* the text the whole time — the same table's FTS5 index
included `problem, root_cause, solution, verification, content_md`, so the full-text endpoint and
the MCP search gave different answers for the same query, which is what finally gave the bug away.

## Solution

Give the internal loader an explicit, testable contract instead of relying on a default:

```js
const INTERNAL_LESSON_LIMIT = 5000;         // the whole corpus, not a page
const fromD1 = await getWithCache(env, "proxy:lessons:d1", () =>
  fetchLessonsFromD1(env, { limit: INTERNAL_LESSON_LIMIT, rich: true }));
```

and keep the searchable body **out of the public row shape** rather than widening a response field:

```js
const row = { id, title, domain, tags, path,
              description: summary || slice(r.problem, 400) };   // public summary, unchanged
if (richApplied) {
  // worker-internal: the index and the matcher read it, responses never carry it
  row.indexText = [summary, slice(r.problem, 2000), slice(r.root_cause, 1200),
                   slice(r.solution, 1200), slice(r.verification, 600)]
                  .filter(Boolean).join(" ");
}
```

Measured cost over 384 lessons: index 0.35 MB → 1.57 MB, cached payload 0.89 MB — trivial next to
the recall it bought, and the public listing kept its 400-char summaries (`publicLessonRow()` strips
`indexText` by destructuring).

Three more things were needed to make the fix *stick*, each a distinct failure mode:

1. **A freshness check that could not see the fix.** The cron rebuilt the index only when it was
   older than 20h. Deploying a better projection therefore did nothing for up to 20 hours. The
   stored index now records `docCount` and `textMode`, and both a size mismatch and a mode mismatch
   force a rebuild. Rule: when a rebuild input changes, the freshness check must know about it.
2. **An in-isolate memo that outlived the rebuild** (5-minute TTL). The isolate that rebuilt the
   index kept answering from the previous one; the fix has to invalidate its own cache.
3. **A graceful path for a schema that may lag** (`try { richCols } catch { leanCols }`), because
   asking a production database for a column that does not exist should degrade search, not break it.

## Verification

- `GET /api/search-index` went from `docCount 100` to `docCount 384, textMode: rich` after the next
  cron tick, then queries that had failed returned the right lessons:
  `kubectl crashloopbackoff` → `kubernetes-crashloopbackoff-debugging`,
  `exit code 137 OOMKilled` → the same lesson (body-only text),
  `git push rejected non-fast-forward` → `erro-push-git-rejeitado-divergente`.
- A query with no corresponding lesson answered honestly at the time of writing: `no_match` for an
  npm peer-dependency failure. **That example invalidated itself, and the way it did is the most
  useful thing in this section.** The lesson shipped with that query written into this very
  paragraph, the corpus was re-indexed, and the query now returns *this lesson* as its top hit —
  the text that documented the honest miss became the thing that matched. Two consequences worth
  keeping: (1) a verification example that lands in the indexed text is part of the corpus, so any
  query quoted in a lesson stops being an "absent from the corpus" control the moment the lesson is
  merged; (2) verification done before a merge describes the corpus *before* the merge. Use a
  synthetic token for absence checks (something no reader would ever type), and re-check control
  queries after publishing, not only before.
- **Still standing, and worse than the honest-miss claim suggested**: natural-language queries are
  not rejected by the relevance floor. At the time of writing, `how do I bake sourdough bread`
  returned five lessons (only the word `how` exists in the corpus) and `VISION_API_KEY env var not
  set` returned five unrelated lessons with the lesson that actually mentions that variable ranked
  ninth. A floor that admits a document matching one corpus-wide word is not a floor. This is the
  open defect this lesson does **not** claim to have fixed; the ranking fix belongs with an
  IDF-weighted coverage rule, calibrated on a real query set rather than on synthetic indexes.
- The regression tests use a D1 stand-in that **only returns the columns a query asked for** and
  throws on a column it does not have (`D1_ERROR: no such column: x`). Without that, a lean query
  would still hand the test the body text and the test would pass while production stayed broken.
- Reverting each fix made its tests fail (`docCount 100` truncation: 4 failures; body projection:
  1 failure) — a green test that has never been red proves nothing.
- The `/api/lessons` response was diffed for the internal field name to prove `indexText` never
  reaches anonymous callers.

## Detection Heuristics

- **Any `|| <number>` default next to `parseInt(filters.limit, 10)` is a paging decision leaking into
  an internal contract.** Search for `parseInt(...) || ` and check each caller: does the internal one
  pass an explicit limit?
- **Compare a self-reported index size against the source of truth.** `docCount` vs. the number of
  rows/files is a one-line invariant; expose it on a status endpoint so drift is visible without a
  debugger. If two retrieval paths over the same corpus exist (FTS endpoint, BM25 index, in-memory
  matcher), assert they agree on a probe set — divergence is how this was found.
- **`.slice(0, N)` on a field that feeds ranking is a recall ceiling, not a formatting choice.** Mark
  such projections "display only" or split the field: one for display, one for search.
- **A `||` between two fields (`summary || problem`) hides the second one entirely** whenever the
  first is usually present. Check the distribution of the left operand before relying on the
  fallback.
- **"The fix deployed but nothing changed" is usually a cache or a freshness gate.** Enumerate what
  the rebuild/refresh path compares against before assuming the code path ran.
