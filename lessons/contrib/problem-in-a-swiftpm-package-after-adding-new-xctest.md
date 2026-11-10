---
title: "SwiftPM 新增 XCTest 方法后 --skip-build 报 No matching test cases"
domain: "mcp"
tags:
  - "problem"
  - "in"
  - "swiftpm"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4020"
summary_plain: "SwiftPM 新增 XCTest 方法后 --skip-build 报 No matching test cases"
trigger: "SwiftPM 新增 XCTest 方法后 --skip-build 报 No matching test cases"
verify: "After `swift build --build-tests`, `swift test --skip-build --filter <newTestName>` prints \"Executed 3 tests, with 0 failures\" for the three new tests, and the broad filter's count rises by the…"
provenance:
  issue: "#4020"
  source: "MCP intake (mcp), lesson submission converted by the maintainer"
---

## Problem

In a SwiftPM package, after adding new XCTest methods, `swift build` followed by `swift test --skip-build --filter <newTestName>` printed "warning: No matching test cases were run" (or ran an old, smaller test count), so a loop meant to repeat the new tests reported nothing and looked like a pass.

## Root Cause

`swift build` builds only the product targets, not the test bundle. `--skip-build` then runs the previously built `.xctest` bundle, which does not contain the new tests. A broad filter still matches old tests, so the stale bundle can look like a full, passing run.

## Fix

Build tests explicitly before using `--skip-build`: `swift build --build-tests`, then `swift test --skip-build --filter ...`. Or drop `--skip-build`. In scripts, fail the step when the output contains "No matching test cases were run" or when the "Executed N tests" count is lower than expected.

## Verification

After `swift build --build-tests`, `swift test --skip-build --filter <newTestName>` prints "Executed 3 tests, with 0 failures" for the three new tests, and the broad filter's count rises by the number of tests added (63 -> 66 in the observed case).
