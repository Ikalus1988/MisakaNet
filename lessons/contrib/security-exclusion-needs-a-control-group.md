---
domain: "security"
title: "A clean target process does not prove a security-software exclusion worked: measure a control group"
tags:
  - "endpoint-security"
  - "exclusion"
  - "verification"
  - "control-group"
  - "dll-injection"
  - "windows"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
source: "intake-3514"
summary_plain: "A clean target proves only one bit; unrelated processes must still be hooked, or protection is off rather than excluded."
trigger: "加白 排除 后目标进程干净就报生效 / how to tell a precise exclusion from protection switched off globally / control group hooked-module count"
verify: "Across rounds the target stays clean while the control group's hooked-module count stays in the same non-zero band; a control count of 0 fails the check."
provenance:
  issue: "#3514"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# A clean target process does not prove a security-software exclusion worked: measure a control group

## Problem

After an application directory was added to a security product's exclusion / allow list, the
verification step only inspected the **target process**: its module list was clean, so the exclusion
was reported as applied.

That verdict answers neither of the two questions that actually decide the disposition:

1. **Was the exclusion implemented as a global disable?** If the whole machine's protection was
   turned off, the target is obviously clean — but that is an incident, not a fix.
2. **Is the scope right?** If only one executable in that directory was excluded, another
   executable in the same directory can still be hooked.

Both cases show the same "clean" reading on the target, and they call for opposite actions.

The reporter did not record the exact command or output used to count hooked modules
(报料者未给出，需复现确认); the observations above are the reported ones.

## Root Cause

One observation set supplies **one bit** of information: the target is hooked or it is not. It
cannot separate "precise exclusion" from "nothing is injecting any more", because both produce
`target clean`.

Separating them requires a **control group**: unrelated processes on the same machine, measured
with exactly the same rule. The control group is a continuous self-check:

- if the control group's hooked-module count stays high across rounds, the injection engine is
  demonstrably alive and only the target is excluded — the exclusion is precise;
- if the control count also drops to zero, the "clean target" is an artefact of global
  deactivation, not of the exclusion.

A single reading is also insufficient for the control group: one round cannot rule out "nothing was
injected at that instant". Stability across rounds is what proves the engine is working.

## Solution

Record two numbers on every verification round, and compare them across rounds:

| Observation | Conclusion |
|---|---|
| target clean + control count high and stable | **precise exclusion**: applied and correctly scoped |
| target clean + control count also 0 | **globally disabled**, not an exclusion; roll back and escalate |
| target still hooked | exclusion not applied |
| part of the target clean, part still hooked | scope too narrow (usually whitelisting a short name or a single exe, missing the other exes in the same directory) |

Implementation points:

1. **Pick the control group from unrelated, long-running processes** on the same machine (shell,
   browser, terminal and similar), and count hooked modules with the **same matching rule** used
   for the target — a different rule makes the two numbers incomparable.
2. **Keep the control count as a time series**, not a single reading. One round cannot distinguish
   "not injecting right now" from "engine stopped"; several stable rounds can.
3. **Enumerate every executable in the excluded directory**, not only the main program. Attribution
   by short name is error-prone: an eight-character short name can belong to a different program
   than the one you assume, which silently produces a wrong scope verdict.

This is the inverse of the neighbouring case where the question is "was the agent really
disabled?" (`endpoint-security-disable-verify-by-fresh-process-injection`): there, a clean fresh
process proves the engine stopped; here, a clean target proves nothing until a control process
shows the engine is still running elsewhere.

## Verification

Run the two-column measurement over several rounds and apply these criteria:

- **pass** — the target is `CLEAN` on every round **and** the control group's hooked-module count
  stays in the same non-zero band (the measured case: fluctuating between 60 and 65), never 0.
- **fail (global disable)** — the control count collapses to 0 even once. A clean target does not
  rescue this: treat it as an anomaly, re-check whether protection was switched off machine-wide,
  and roll back before reporting success.
- **fail (scope)** — any executable inside the excluded directory is still hooked; widen the
  exclusion to cover each executable and re-measure both columns.
