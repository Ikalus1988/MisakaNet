---
domain: "development"
title: "Judge a fix by how the failure degrades, not by whether a crash remains: count the trigger signature"
tags:
  - "fix-verification"
  - "crash-triage"
  - "trigger-signature"
  - "soft-fault"
  - "endpoint-security"
  - "acceptance"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
source: "intake-3481"
summary_plain: "A fix can remove the deterministic crash yet leave a rarer one or a new soft fault; judge the failure mode."
trigger: "36 秒必崩 after exclusion 150 秒不崩但仍 2 轮崩 1 轮 / new SYST-302 soft fault after the crash disappeared / crash count down but trigger signature unchanged"
verify: "After the fix the trigger signature still appears in every round while the crash does not: report effective-but-incomplete, not fixed."
provenance:
  issue: "#3481"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# Judge a fix by how the failure degrades, not by whether a crash remains: count the trigger signature

## Problem

Verifying a fix invites two opposite mistakes:

1. **"It still crashes, so the fix did nothing."** The failure may already have moved from
   deterministic to low-rate; the fix is real but incomplete.
2. **"It stopped crashing, so it is cured."** This misses the softer residue that only becomes
   visible once the crashes are gone.

Measured case: a simulation environment crashed deterministically because of a three-layer
endpoint-security stack (activating the teach pendant crashed the controller after roughly 36 s).
IT excluded one of the three layers and the retest looked like a different problem:

- the deterministic path no longer crashed — a 150 s window stayed clean;
- idle rounds still crashed **1 out of 2 rounds**;
- the log gained a **soft-fault signature that never appeared on the crash path** — the controller
  reported a "please power off" state (`SYST-302`, 5 occurrences) without throwing an exception.

Judging by "crashed or not" gives "fix invalid" or "fixed", and both are wrong.

The reporter did not provide the raw controller log or the exact reproduction commands
(报料者未给出，需复现确认); the numbers above are the reported ones.

## Root Cause

Crash verdicts are **binary** (crash / no crash), while a fix's effect is usually **continuous**
(it may move the rate from 100% to 30%). A binary criterion cannot measure a continuous effect, so
it must misreport in one direction or the other.

A second mechanism hides behind the first: once crashes disappear, faults that were masked by the
crash surface. Crashes are loud (stack, crash offset); soft faults are quiet (a status code, a
power-off prompt, a hung task) and do not match crash regexes, so a crash-count-only verification
silently drops them.

Finally, crash rate is a poor anchor for "is the residual trigger still present": it is noisy and
depends on how long the test window runs.

## Solution

Judge by **whether the failure mode degraded**, not by whether a failure exists, and count the
**trigger signature** alongside the crash signature:

| Retest observation | Correct conclusion |
|---|---|
| deterministic path still crashes, crash offset unchanged | fix ineffective (or not applied) |
| deterministic path clean, but still probabilistic crashes with the same offset | **effective but incomplete**; residual trigger source remains |
| no crash, but a new status-class soft-fault signature appears | **degraded to a soft fault**; risk not removed, only reshaped |
| no crash, no new signature, connection-reset trigger signature gone too | cured |

Two companion rules:

1. **Count the trigger signature, not only the crash signature.** The trigger signature (e.g. a
   connection-reset error code, a "deny" line in the policy log) appears earlier than the crash,
   appears on *every* reproduction, and does not depend on crash probability. In the measured case
   it was present in all 3 rounds while the crash appeared in only 1 — far more stable for judging
   whether the trigger source is gone.
2. **After crashes vanish, deliberately search for new status-class signatures** (power-off prompts,
   assertions, task hangs). They do not match crash patterns and are otherwise lost.

## Verification

Apply the table to a retest that records three columns per round: crash count, trigger signature,
and status-class soft-fault signatures.

- Pass for **incomplete**: the deterministic path went from "crashes within N seconds" to "clean
  for M minutes", with M several times N, **while the trigger signature is still present**. Report
  "effective but incomplete" and name the residual trigger source (the reported one: a WFP loopback
  interception).
- Pass for **degraded**: no crash, but new soft-fault signatures; list them explicitly.
- Pass for **cured** only when both the trigger signature and the crash signature are zero across
  the rounds; anything else keeps the ticket open.
