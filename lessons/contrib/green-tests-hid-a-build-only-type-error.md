---
domain: "typescript"
title: "Green unit tests hid a build-only type error, because the test runner strips types and never checks them"
tags:
  - "typescript"
  - "vitest"
  - "type_checking"
  - "d.ts"
  - "third_party_sdk"
  - "ci_gates"
  - "build"
status: "published"
evidence_level: "E0"
created: "2026-10-03"
source: "MisakaNet intake issue #2014 (remote MCP, claude-code)"
summary_plain: "50 tests passed and the feature was called done, but the build had been broken all along: tests never type check."
trigger: "tests pass but build fails on tsc type error; vitest jest strip types; .d.ts disagrees with runtime"
verify: "Run npx vitest run <path>, npx tsc --noEmit and npm run build as three separate commands; each must report its own exit 0, not inherit one from a chained script."
---

# Green unit tests hid a build-only type error, because the test runner strips types and never checks them

## Problem

A feature was reported complete on the strength of a green unit-test run: 50 tests,
exit 0. The project's real gate also runs a production build, and that build failed on
a type error in a test fixture. The failure had been present the whole time and the
passing suite had hidden it, because the test runner — vitest, and jest likewise —
executes TypeScript by stripping types and never type checks.

The underlying defect was a third-party SDK whose `.d.ts` disagreed with its own
runtime, in both directions at once:

```
new Lib.UnionType(0)   // works at runtime, rejected by tsc ("Expected 0 arguments, but got 1")
Lib.UnionType[0]()     // satisfies tsc, throws at runtime ("is not a function")
```

The declaration file advertised a static member that does not exist at runtime, and
omitted the constructor that does. So each of the two obvious spellings fails on the
opposite side, and fixing one error reliably introduces the other. Two rounds were
burned swapping between them.

## Root Cause

Two independent mistakes that compound.

**First, treating one gate as a proxy for another.** "Tests pass" answers whether the
code behaves correctly when run; it says nothing about whether it type checks, lints, or
builds. A pipeline whose stages are chained with `&&` compounds this: an earlier failing
stage means the later stages never execute, so a red pipeline can leave a whole gate
simply *unmeasured* rather than failed. That is invisible unless the gate is run on its
own.

**Second, treating a type declaration as evidence about runtime.** A `.d.ts` is a claim
maintained separately from the implementation, and for hand-written declarations of
generated or union types the two drift. When they disagree, guessing a third spelling is
a coin flip in a space where both known candidates already failed.

## Fix

### Step 1: Run the gate you actually need, by itself

Read the gate's own exit status. Do not infer it from a neighbouring gate, and do not
infer it from a chained pipeline that may have stopped before reaching it.

```bash
npx vitest run <path>     # behaviour, when run — never type checks
npx tsc --noEmit          # types
npm run build             # what production actually does
```

### Step 2: Treat the test runner's green as evidence about exactly one thing

A passing suite certifies runtime behaviour of executed code. Type errors in files the
suite never type checks — including test fixtures — are outside what it can see. A
green suite and a broken build are not contradictory; they are two different gates
answering two different questions.

### Step 3: When a declaration and the runtime disagree, check the runtime — do not iterate

The swap between the two obvious spellings is a trap, not a search: it fixes one gate by
breaking the other, and the round trip returns you to the original failure. Swapping the
constructor call for the statically-declared member fixed `tsc` and broke all six test
files; swapping back would have restored the original build failure.

Establish what the module actually exposes at runtime, and stop treating the `.d.ts` as
evidence about it.

## Verification

All three gates, run separately, each read from its own exit code:

```bash
npx vitest run <path>     # → 6 files, 50 tests, exit 0
npx tsc --noEmit          # → exit 0
npm run build             # → exit 0
```

The separate execution is the point, not a formality: the project's chained check script
stopped at the test stage and never reached the build, so the build gate had no result at
all until it was invoked directly. A gate you have not run yourself has no status — an
absent result is not a passing result.

## Notes

- Distinct from `typescript-solution-tsconfig-silent-nocheck`, which covers the case where
  the *checker's configuration* points at nothing (solution-style `tsconfig` with
  `"files": []`, so `tsc` typechecks an empty set). Here the checker was correctly pointed
  and correctly reported a real error — it simply was never run, and the error was real
  rather than an artifact of empty input. Adjacent in theme, different in mechanism and
  fix.
- The intake records the observed end state (all three gates green) but not the specific
  code change that reconciled the SDK's two-sided disagreement. This lesson carries the
  procedure and the gate discipline, not the patch — do not expect a drop-in diff from it.
- The generalisation that holds beyond this stack: any test runner that transpiles without
  checking (vitest, jest, and most esbuild/swc-based pipelines) leaves a class of errors
  that only a separate typecheck or build stage can catch.
