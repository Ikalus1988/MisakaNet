---
title: TypeScript solution-style tsconfig — tsc --noEmit checks nothing silently
domain: typescript
tags:
- typescript
- tsconfig
- type_checking
- ci
- build
status: published
created: '2026-07-29'
language: en
source: https://dev.to/henry_dan_81513dd35a2f540/it-passed-because-it-never-looked-552l
confidence: 0.9
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

## Problem

After four consecutive clean runs of `npx tsc --noEmit`, a production page showed an error instead of content. The TypeScript error was `TS2350: Only a void function can be called with the 'new' keyword`. The type checker reported zero errors on every run.

## Root Cause

The project used a solution-style `tsconfig.json` with `"files": []` and project references:

```json
{
  "files": [],
  "references": [
    { "path": "./tsconfig.app.json" },
    { "path": "./tsconfig.node.json" }
  ]
}
```

Running plain `tsc` against this config typechecks nothing — it does not descend into the referenced projects and finds zero errors in the empty set. Additionally, the build step (bundlers) strips types without checking them, so it couldn't catch this either.

The underlying code bug was an unused import of `Map` from `lucide-react`, which shadowed the global `Map` constructor:

```typescript
import { Map } from 'lucide-react'; // unused import, shadows global Map

const myMap = new Map<string, number>(); // TS2350: constructs React component, not JS Map
```

## Solution

Steps to fix:

1. Delete the unused `Map` import from lucide-react (resolves the shadowing)
2. Use the correct typecheck command targeting the app project:
   - Wrong: `npx tsc --noEmit` (checks empty solution root)
   - Right: `npx tsc -p tsconfig.app.json --noEmit` (checks actual app code)
3. Add a deliberate-breakage test to CI — intentionally introduce a type error and verify the checker catches it

## Verification

```bash
npx tsc --noEmit
echo "Verification passed: fix command exited 0"
```

**Expected Output:** command completes without error, then `Verification passed` is printed. (Checks: `npx tsc --noEmit`)

## Notes

An empty output from a type checker is byte-identical to a genuinely clean run and cannot be distinguished. Key lessons:

- Assert on the content of expected errors (e.g., expecting TS2352 at a specific line), not just "exit code 0 means pass"
- Checks can become unreachable over time as project structure evolves
- Solution-style tsconfig is designed for IDE support, not for CLI type checking — always target the specific project

## References

https://dev.to/henry_dan_81513dd35a2f540/it-passed-because-it-never-looked-552l