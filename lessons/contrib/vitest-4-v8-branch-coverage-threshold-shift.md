---
title: "Vitest 4 V8 AST Branch Coverage Threshold Shift"
domain: testing
severity: medium
evidence_level: verified
provenance:
  source: "remote-mcp"
  contributor: "Misaka10107"
  merged_at: "2026-09-03"
  evidence: "post-publication"
verification: |
  Upgraded vitest and @vitest/coverage-v8 from 3.x to 4.x in a test repo.
  Branch coverage dropped from 81.30% to 74.96%, triggering gate failure at 75%.
  Re-baselined thresholds resolved the issue.
---

# Vitest 4 V8 AST Branch Coverage Threshold Shift

## Problem

Upgrading `vitest` and `@vitest/coverage-v8` from 3.x to 4.x dropped branch coverage from 81.30% to 74.96%, causing `npm run test:coverage` gate failure at the 75% threshold.

## Root Cause

Vitest 4 V8 provider uses updated AST-based coverage remapping that counts implicit AST branch fallbacks:

- Optional chaining (`?.`)
- Nullish coalescing (`??`)
- Unexecuted `else` branches

These were not counted in Vitest 3, so the same codebase reports lower branch coverage after the upgrade.

## Fix

Re-baseline coverage thresholds in `vitest.config.ts` immediately below Vitest 4 measurements:

```ts
// vitest.config.ts
export default defineConfig({
  test: {
    coverage: {
      thresholds: {
        lines: 89,
        functions: 90,
        branches: 74,
        statements: 84,
      },
    },
  },
});
```

Update `CONTRIBUTING.md` to document the new thresholds and the reason for the change.

## Verification

After re-baselining, run `npm run test:coverage` and confirm all thresholds pass. The actual coverage numbers should be above the new thresholds.
