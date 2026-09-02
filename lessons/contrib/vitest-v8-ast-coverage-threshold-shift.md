---
title: Vitest 4 V8 AST Coverage Remapping Shifts Branch Coverage Below Threshold
domain: testing
tags:
- vitest
- coverage
- v8
- ast
- branch-coverage
- testing
status: published
created: '2026-08-29'
language: en
source: intake-issue-1384
evidence_level: E0
---

## Problem

Upgrading `vitest` and `@vitest/coverage-v8` from 3.x to 4.x dropped branch coverage from 81.30% to 74.96%, causing the `npm run test:coverage` gate to fail at the 75% threshold — even though no test code changed.

## Root Cause

Vitest 4's V8 provider uses an updated AST-based coverage remapping that counts *implicit* AST branch fallbacks:

- optional chaining (`?.`) branches
- nullish coalescing (`??`) branches
- unexecuted `else` branches

These implicit branches did not count against coverage in Vitest 3.x, so the same test suite now reports lower branch coverage purely from the provider's stricter instrumentation — a measurement change, not a regression in test quality.

## Solution

Re-baseline the coverage thresholds in `vitest.config.ts` immediately below the Vitest 4 measurements, then update `CONTRIBUTING.md` so the documented expectations match.

### Step 1 — Measure under Vitest 4

```bash
npm run test:coverage
```

Record the actual Vitest 4 percentages (example: 89% lines, 90% functions, 74% branches, 84% statements).

### Step 2 — Re-baseline thresholds

```ts
// vitest.config.ts — set thresholds just below measured Vitest 4 values
coverage: {
  thresholds: {
    lines: 88,
    functions: 89,
    branches: 73,
    statements: 83,
  },
}
```

Choose values *below* the measured numbers so the gate passes with a small safety margin, not above them.

### Step 3 — Update CONTRIBUTING.md

Replace any "coverage must be ≥ 75% branches" style guidance with the new thresholds, and note that Vitest 4 counts implicit AST branches (the numbers are not directly comparable to Vitest 3.x).

## Verification

```bash
npm run test:coverage
# Coverage gate passes (no threshold violation)
git diff vitest.config.ts  # shows the re-baselined thresholds only
```

## Notes

- The drop is a provider measurement change, not lost test quality — do not add tests just to chase the old number.
- When upgrading Vitest again, expect another threshold shift; re-measure before re-baselining.
- Related: any coverage gate tied to a single composite threshold is fragile — prefer per-metric thresholds (`lines` / `functions` / `branches` / `statements`).
