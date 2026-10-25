---
title: "A module-scoped pytest fixture shares one mutable clone, so execution order decides green or red"
domain: "testing"
tags:
  - "pytest"
  - "fixture-scope"
  - "test-isolation"
  - "order-dependence"
  - "pytest-randomly"
  - "regression-guard"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "module 级 fixture 把一个可变副本共享给三个测试，写坏它的测试先跑，基线测试就失败；同一个 commit 靠随机顺序时红时绿。"
trigger: "the committed corpus does not match its own generators AssertionError pytest-randomly module scope fixture shared mutable clone depends on the previous test"
verify: "回归守卫测试按「先跑破坏性测试」的顺序重跑三个测试，输出 3 passed 且无 skip；把 fixture 改回 scope=module 该守卫转红（内层 2 failed, 1 passed）"
source: "intake-3531"
provenance:
  issue: "#3531"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

## Problem

A pytest fixture declared with `scope="module"` handed the **same mutable clone** to three sandbox tests. A mutator test wrote a probe file and ran the generators; the baseline test then inspected the same clone and failed with:

```
AssertionError: the committed corpus does not match its own generators
```

on a corpus that was in fact clean. Because `pytest-randomly` reshuffles each run, the same commit went green or red depending on execution order. One test even encoded the dependency as accepted fact:

```
pytest.skip("depends on the previous test's probe")
```

## Root Cause

A module-scoped fixture is created once per module and shared by every test in it, so a *mutable* clone stops being a fixture and becomes shared state. The assertion is not wrong and the corpus is not dirty — the baseline test read residue the mutator left behind.

Two aggravating factors turn a plain isolation bug into a flaky one:

- **Order is not a guarantee.** `pytest-randomly` reorders tests each run, so "it passes when I run it" only means "it passed in that order".
- **The `skip` hid the failure.** The order dependency was written down as a legitimate skip, so in the one order that would have failed, the test silently skipped instead — and would have stayed a permanent green skip even after the sharing was removed.

The reporter did not include the fixture or test source, so the exact module path and clone body are not reproduced here.

## Solution

Three-part fix:

1. **Function scope.** Change the fixture from `scope="module"` to function scope so each test gets its own clone. A per-test copy costs one directory copy per test and removes the class of failure entirely.
2. **Make the dependent test self-contained.** It should create its own probe fixture data instead of relying on a previous test's leftovers, and the `pytest.skip("depends on the previous test's probe")` must be deleted — once the sandbox stops being shared, that skip becomes a permanent green lie.
3. **Add a regression guard** that spawns a subprocess running the three tests **in the order that used to fail** (mutator first) and asserts `3 passed` with no skips. The guard runs the inner suite in a fixed order, so a shared-state regression surfaces no matter what the outer run order happens to be.

## Verification

Reporter-measured results:

- Two-test repro (mutator then baseline) with `-p no:randomly`: **red before** (baseline fails on the residue), **green after** (2 passed).
- The three sandbox tests run mutator-first: **3 passed**.
- Temporarily reverting the fixture to `scope="module"` makes the guard test go **red** (inner run: 2 failed, 1 passed) — this is the proof that the guard actually bites, not just that it exists.
- Full file green after the fix: **10 passed**.

Read the guard's own inner output, not only its outer pass/fail: a guard that spawns a subprocess can pass while the inner run skipped.
