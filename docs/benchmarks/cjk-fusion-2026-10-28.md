# CJK fusion: gate replaced, measured in production (2026-10-28)

**Status:** deployed experiment, one change, with a config rollback. It answers the question
[`embedding-ab-2026-10-27.md`](embedding-ab-2026-10-27.md) left open: *the vector path is worth ~18
points and a stronger model ~9 — so is the lever the model or the gate?* It was the gate.

## The change

`workers/register-proxy-sw.js` ran the semantic path **only when BM25 returned nothing**
(`if (!results.length)`), so a confident-but-wrong lexical hit suppressed it entirely — measured
2026-10-27: 13 of 20 misses were exactly that. For queries containing CJK characters the two lists
are now fused with reciprocal-rank fusion instead of one gating the other.

- **RRF, not score blending.** BM25 is an unbounded lexical sum, cosine is bounded; a weight between
  them would need tuning per language, which is the mistake #2250 recorded four times.
- **Vector floor 0.45**, not the 0.62 `no_match` floor: fusion asks "plausibly the same subject",
  where a near miss is a useful second opinion rather than a wrong answer.
- **CJK only.** English already sits below its floor and this experiment measured no English arm.
- **Rollback is a variable:** `MISAKANET_CJK_FUSE=0`, the same switch shape as `MISAKANET_SEMANTIC=0`.
- **Cost is real:** every CJK query now pays one embedding plus one Vectorize query it did not pay
  before.

## Expected before deploying

Simulated offline against production's own delivered rankings for the 64 Chinese queries, fused with
the same `bge-m3` vectors the worker holds: R@1 **0.556 → 0.698** overall, cross-lingual
**0.424 → 0.636**, 11 queries fixed and 2 broken.

## Measured after deploying (`08db81ec`)

64 Chinese queries against the live endpoint, 0 transport failures:

| bucket | n | before | after | Δ |
|---|---|---|---|---|
| zh → zh | 31 | 0.710 | **0.774** | +6.4 pp |
| **zh → en** | 33 | 0.455 | **0.697** | **+24.2 pp** |
| zh → en / low overlap | 14 | 0.214 | **0.500** | +28.6 pp |

The live result beat the simulation on the cross-lingual bucket (+24.2 vs +21.2 points), which is the
expected direction: the simulation could only fuse with the rankings production had already returned,
while the deployed path fuses before the top-5 is cut.

The repo's own floor bench agrees on direction: **zh hit@1 12/22 → 15/22**, hit@3 16/22 → 17/22.

## The English question, answered stably

Three consecutive floor-bench runs on the same commit now read **identical**: English **15/20 hit@1 ·
19/20 hit@3** against a floor of 16/19, Chinese 15/22 · 17/22.

Two things follow, and the second was a bug:

1. **The fusion did not move English.** It cannot: the fuse is gated on CJK characters and no English
   bench query contains any. English was below its floor *before* this change and is at the same place
   after it.
2. **The earlier readings of 14/20 and 12/20 were not measurements.** `bench_production_recall.py`
   counted a request that exhausted its retries as a miss. Fixed in #3984 (excluded from the
   denominator; a run with errors now reports "not comparable" instead of a floor verdict). Anything
   quoting 12 or 14 from that tool before 2026-10-28 is quoting a flaky connection.

## What this does not show

- **One query set, one day.** 64 Chinese queries, generated from the lessons they target; the
  cross-lingual bucket is n=33. The direction is consistent across the simulation, the live probe and
  the floor bench, but the third decimal is not a stable estimate.
- **No English arm was measured.** The claim is scoped to CJK precisely because widening it would
  spend the gain on an unmeasured risk.
- **Latency and cost per CJK query were not measured.** The change adds an embedding call and a
  Vectorize query to a path that previously skipped both on a hit. That is a deliberate trade, not a
  measured one.
- **Two regressions in the simulation** (a query that had rank 1 and lost it) are inside the numbers,
  not excluded from them.

## Reproduction

```bash
python3 scripts/bench_zh_crosslingual.py --attempts 5      # the 64-query buckets above
python3 scripts/bench_production_recall.py --attempts 5    # the floor bench (stable, see #3984)
```

`--attempts 5` is not optional on a flaky path: with the default of 3 this bench produced 15, 14 and
12 on one commit.
