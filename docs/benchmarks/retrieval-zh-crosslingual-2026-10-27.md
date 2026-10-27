# zh retrieval on the live path — same-language vs cross-lingual (2026-10-27)

**Status:** one-off measurement, not a leaderboard and not a gate. It exists to settle one open
question in `docs/maintainer/handoff-2026-10-27.md` §2.2 before anyone spends a round on it.

**Question:** the handoff proposed CJK tokenisation as the next Chinese lever, from a 3/15 (20%)
sample. But a Chinese query aimed at an English lesson is *cross-lingual*: no amount of CJK
tokenisation helps it, because the target contains no CJK characters to match. Half of the zh
queries in the L1-267 query set are that kind. So does one "Chinese recall" number describe a
problem the tokenizer owns, or is it averaging two different problems?

## Method

- **Queries:** the 64 `zh` rows of the [L1-267 query set](retrieval-l1-267-queries.jsonl). Same
  queries, same targets as the published L1-267 run — so the two are comparable row for row.
- **Bucketing:** each query is filed by the **target lesson's** language, decided from the lesson
  body (share of CJK characters among non-whitespace characters of the first 1500 chars > 0.25).
  Frontmatter is skipped on purpose: its tags are English even on Chinese lessons.
- **Endpoint:** the live production MCP (`https://misakanet.org/mcp`), `top: 5`,
  `detail: compact`, 2.1 s between queries (≈28/min, under the 30/min burst guard). Up to 5
  transport retries per row; rows that still fail are **excluded from every denominator** and
  counted in their own field.
- **Scoring:** the target lesson counted at rank 1/3/5. Anything else is a miss, including a miss
  that returned five other lessons — the two are reported separately below.
- **Index state at run:** `GET /api/search-index` reported 651 docs, `textVersion: 5`,
  `cjkChannel: {version: 1, docCount: 651, termCount: 22583}`, built 2026-10-27T11:49:22Z.

## Results

| bucket | n | R@1 | R@3 | R@5 | no_match | semantic path served | misses that returned a wrong lesson | misses with no results |
|---|---|---|---|---|---|---|---|---|
| zh → zh | 31 | **0.710** | 0.742 | 0.774 | **0.032** | 25.8% | 6 | 1 |
| zh → en | 33 | **0.455** | 0.576 | 0.606 | **0.182** | 36.4% | 7 | 6 |

By overlap (the bucket that decides where the loss sits):

| bucket | n | R@1 | no_match |
|---|---|---|---|
| zh → zh / high | 18 | 0.833 | 0.056 |
| zh → zh / low | 13 | 0.538 | 0.000 |
| zh → en / high | 19 | 0.632 | 0.105 |
| zh → en / low | 14 | **0.214** | 0.286 |

## Findings

1. **Same-language Chinese is not broken.** 0.710 R@1 and a 3.2% `no_match` rate on the live path.
   The CJK channel is deployed and carrying its weight (`cjkChannel.version: 1`); CJK-1…CJK-4
   (#2355–#2358) closed in late September. The repository's own floor bench agrees: run on the same
   day, the 22 CJK queries scored 12 hit@1 (floor 11) and 16 hit@3 (floor 15) — passing, and roughly
   flat against the 2026-09-28 baseline of 11/22 · 14/22.

2. **The loss is concentrated in cross-lingual, low-overlap queries.** 0.214 R@1 with 28.6%
   `no_match`: this is the one bucket where a Chinese speaker asking about an English lesson gets
   nothing useful four times out of five. It is also the bucket that CJK tokenisation cannot reach
   by construction.

3. **20% of all misses are confident-but-wrong, and those never see the semantic path.** 13 of 64
   rows returned a non-empty result set that did not contain the target (6 same-language, 7
   cross-lingual). `register-proxy-sw.js` runs the semantic fallback **only on an empty BM25
   result** — "a hit is never re-ranked" — so a confident wrong lexical hit suppresses the vector
   path entirely. The remaining 7 misses returned nothing at all, where the fallback did run and did
   not clear the 0.62 floor.

4. **One envelope inconsistency, recorded because it silently changes this measurement's own
   attribution.** `misakanet_search` can return `{no_match: true, results: [], source:
   "worker-bm25+semantic"}`. Reproduced deterministically (query: `提交代码时总是显示一个红色的检查标志，无法通过验证`).
   Reading the code, `source` is set when the semantic path produces hits, but the kind filter and
   the FAQ merge run *afterwards* and can empty the set; the `no_match` reply then reports the stale
   `source`. Consequence: `servedBy.semantic` counts "the vector path produced hits", not "the
   caller got vector results". Not fixed here — the right semantics is a product decision (report
   the matcher, or report what was delivered), and this measurement only needed to know which.

## What this does not show

- **Not the 80-sample audit's 3/15.** Those were real user queries, whose overlap with the corpus is
  not the synthetic set's. This measures lesson-derived queries; that distribution is easier to hit
  and this run says nothing about whether real Chinese queries improved.
- **n = 31 / 33.** A single run; each bucket is ±~16 points at 95% confidence. The gap between
  buckets is larger than that, the third decimal place is not.
- **Not an A/B.** The CJK channel and the semantic fallback are both live in this path, so nothing
  here separates their contributions. The L1-267 arms are the place to read that — with the caveat
  that its eval corpus was not refreshed and neither arm isolates the CJK channel.
- **Not a verdict on the lessons.** A miss can be a stale target, a badly generated query, or a
  ranking failure; the per-row data is published so a human can tell them apart. Nothing here
  decides which.

## Verdict

The handoff's §2.2 lever is misfiled. **Do not spend the next round on CJK tokenisation** — it is
shipped, it is live, and same-language Chinese retrieves at a healthy rate. The measured weakness is
the cross-lingual, low-overlap corner, and the mechanism that would help it (the vector path) is
gated behind a condition that a wrong lexical hit satisfies. The next experiment is therefore
**arbitration between a confident lexical hit and the semantic path**, measured on this bucket
(zh → en / low, n = 14), with the English floors held still — not a tokenizer change and not a
global `SEMANTIC_MIN_SCORE` move.

One caution from the same day's floor bench: production English came in at 15/20 hit@1 against a
floor of 16, so anything that touches the lexical path has to be checked against English too.

## Artifacts

- [Machine-readable report](retrieval-zh-crosslingual-2026-10-27.json) — summary + every row
  (query, returned ids, rank, `no_match`, `source`, retries).
- `scripts/bench_zh_crosslingual.py` — the probe; `tests/test_bench_zh_crosslingual.py` covers
  everything except the network.

```bash
python3 scripts/bench_zh_crosslingual.py --attempts 5 \
  --out docs/benchmarks/retrieval-zh-crosslingual-2026-10-27.json
```

Two traps this probe hit, so the next person does not re-hit them: the edge answers
`Python-urllib/3.x` with **403** while `curl` gets 200 (`docs/agents/repo-operations.md` §4), so the
`User-Agent` is load-bearing; and a local `https_proxy` that drops connections is indistinguishable
from the endpoint serving empty bodies — the first run lost 20 of 64 that way and would have read as
a 31% recall disaster.
