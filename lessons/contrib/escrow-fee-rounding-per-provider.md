---
{
  "title": "Banking-style escrow fee estimate has a per-provider rounding disparity",
  "domain": "development",
  "tags": [
    "payments",
    "calculation",
    "rounding",
    "precision",
    "ledger"
  ],
  "status": "published",
  "evidence_level": "E2",
  "created": "2026-08-11 00:00:00 UTC",
  "updated": "2026-08-11 00:00:00 UTC",
  "author": "Liona Can",
  "source": "manual",
  "edited_at": "2026-08-21T13:12:59+08:00",
  "merged_by": "Liona Can"
}
---

# Escrow fee estimates round differently per provider — and it silently changes totals

## Problem

A payout/reward schema recorded a fee estimate computed with floating-point math, while the escrow engine (and the human maintainers) expected per-provider integer-percent rounding. Invoices, reward cells, and gateway payloads diverged by a few basis points — invisible on a single row, yet every cross-check and tally disagreed.

## Root cause

Money math was done as `amount * rate` in binary floating point and then summed, instead of using currency-centric integer arithmetic (cents/wei/sats) with explicit rounding at the end. Two compounding effects:

- `0.1 * 3` style products are not exact in binary floats (e.g. `0.30000000000000004`), so *identical* fee logic produced *different* totals depending on provider defaults and where the rounding was applied (per-row vs. at-the-end).
- A schema that allows the number of decimal places to differ per provider makes the same invoice look correct under one and wrong under another.

## Failure & recovery

The failure surfaced only when an independent audit added totals and compared them to the stored fee. The recovery checklist:

1. Move all money arithmetic to integer units (cents, sats, or the token's smallest unit).
2. Choose a single rounding mode (and mention it: round-half-up, truncation, banker's rounding).
3. Sum in integer units, round once at the end, never per-row mid-computation.
4. Add a "recompute and compare to stored" invariant check in tests.

## Lesson

Fee/escrow math is currency math: use integer units, apply one rounding policy, and validate stored totals by recomputation. "It's almost right" is how payment bugs get shipped.
