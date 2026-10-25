---
domain: "testing"
title: "Classify a crash by its signature first, and only then by its rate: two rounds cannot call it flaky"
tags:
  - "crash-triage"
  - "flakiness"
  - "reproducibility"
  - "sample-size"
  - "signature-fingerprint"
  - "verification"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
source: "intake-3518"
summary_plain: "Two rounds cannot tell a deterministic crash from a flaky one; compare the signature fingerprint before the rate."
trigger: "2 轮 1 崩 judged probabilistic 偶发 / crash time differs every run 345s 465s 600s / is this deterministic or intermittent"
verify: "Across 5+ rounds the count vector and crash offset are identical each run, and every rate claim carries its round count instead of a 2-round sample."
provenance:
  issue: "#3518"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# Classify a crash by its signature first, and only then by its rate: two rounds cannot call it flaky

## Problem

While triaging a crash, the reporter ran **two rounds, saw one crash**, and concluded the failure
was `概率性偶发` (probabilistic / intermittent) — the wording went as far as preparing to downgrade
the ticket. Three more rounds were run afterwards and the real picture was **4 crashes in 5 rounds**.

The same session contains the opposite error. The crash timestamp was different every run
(`345s` / `465s` / `600s`), which was read as "random failure, no pattern", so nobody dug for a root
cause. Yet when the runs were lined up, the **signature fingerprint was identical line by line**:
the same counter vector and the same crash offset on every run.

The reporter did not supply the raw crash log or the command sequence used to produce these rounds
(报料者未给出，需复现确认); the numbers above are the reported counts.

## Root Cause

Two independent questions were answered with one measurement:

1. **Does it happen at all?** This is a rate. Estimating a rate needs rounds, and two rounds give
   almost no information: `1/2` became `4/5` once three more rounds were added.
2. **What does it look like when it happens?** This is a fingerprint — the full count vector
   (crash count, each exception code, per-module abort counts, reconnect count) plus the crash
   offset. It usually stabilises within one or two rounds, and it localises the root cause far
   better than the rate does.

Using a small sample of axis 1 to answer a question about axis 2 (or the reverse) produces a wrong
disposition in both directions: "flaky, downgrade it" and "random, don't investigate it".

A different crash *time* is not a different bug. Time is set by external conditions (how long the
trigger path takes to reach the same fault); the fault itself is fixed by the code path.

## Solution

Decide in two steps, and never let one step stand in for the other.

**Step 1 — is the signature fingerprint stable across rounds?**

Record per round, not per ticket:

- crash count;
- the count of every distinct exception code;
- per-module abort counts;
- reconnect count;
- the crash offset (module + address/offset).

If the vector is identical across rounds and the offset matches, it is **one deterministic root
cause**, whatever the rate is. Write the root cause into the ticket at that point; do not wait for
more rounds.

**Step 2 — how many rounds before claiming "probabilistic"?**

To call a failure probabilistic you must see both outcomes alternate with a roughly stable ratio.
Two rounds cannot show that. The practical floor is **at least 5 rounds**, and the claim must name
the trigger path it was measured on — rates from different trigger paths must not be pooled.

| Observation | Conclusion |
|---|---|
| Fingerprint identical + high rate | deterministic bug, trigger moment depends on the environment, must be fixed |
| Fingerprint identical + low rate | still the same bug, only harder to trigger; **not** evidence of a fix |
| Fingerprint differs between rounds | possibly several distinct problems; split them before triaging further |
| Fingerprint changed after a fix | the fix moved the crash path; re-confirm whether it degraded to a soft fault |

Corollary: if "the crash got rarer" but the fingerprint is unchanged, the root cause is still
there. That is **effective but incomplete**, not **fixed**.

## Verification

The cross-round table must carry both columns at the same time:

- **signature vector** — count vector plus crash offset, per round;
- **rate** — occurrences out of the total number of rounds, with the round count written down
  (`4/5`, not "about 80%").

Pass criteria, in order:

1. Fingerprint identical across rounds → the root cause can be stated now, regardless of rate.
2. Any "flaky / intermittent" claim that is not backed by at least 5 rounds and a named trigger
   path fails the check and must be rewritten as "sample too small".
3. A fix is accepted only after 5+ rounds in which **both** the crash signature and the trigger
   signature are zero. A lower rate with the same fingerprint is reported as effective-but-
   incomplete.
