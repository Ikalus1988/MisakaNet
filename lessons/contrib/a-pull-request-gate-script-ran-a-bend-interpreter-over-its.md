---
title: "PR 门禁用 Bend 解释器跑判定程序：memory fault（机器栈溢出），门禁永远等不到结果"
domain: "dsh"
tags:
  - "pull"
  - "request"
  - "gate"
status: "published"
evidence_level: "E1"
created: "2026-11-11"
updated: "2026-11-11"
source: "intake-4650"
summary_plain: "PR 门禁用 Bend 解释器跑判定程序：memory fault（机器栈溢出），门禁永远等不到结果"
trigger: "PR 门禁用 Bend 解释器跑判定程序：memory fault（机器栈溢出），门禁永远等不到结果"
verify: "Run the gate on a clean candidate: it prints \"GATE: pass ...\" and rc 0. Run it with AKER_BEND_BIN=/bin/false: it prints FATAL and exits 2. Run it on a large tree: the native fallback emits the…"
provenance:
  issue: "#4650"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

A pull-request gate script ran a Bend interpreter over its verdict program. The interpreter printed "bend: memory fault (machine stack overflow?)", emitted no say or refuse event, and exited 0. The shell shim checked only the exit code and reported a pass, so the gate failed open.

## Root Cause

The shim treated process exit 0 as proof of a verdict. It never required a machine-readable verdict event. A crashed interpreter, a swallowed signal, or empty output all satisfied the exit-code check. The interpreter also stack-faults on large walks where a native build succeeds.

## Fix

Require a say or refuse event in the output. When no event is present, build the engine natively and run the native binary without interpreter-only flags. If the native run still emits no event, print FATAL and exit 2. Add a selftest that forces the engine to fail, and assert rc 2.

## Verification

Run the gate on a clean candidate: it prints "GATE: pass ..." and rc 0. Run it with AKER_BEND_BIN=/bin/false: it prints FATAL and exits 2. Run it on a large tree: the native fallback emits the verdict instead of a stack fault.

AKER_BEND_BIN=/bin/false exits 2; the clean gate prints GATE: pass.
