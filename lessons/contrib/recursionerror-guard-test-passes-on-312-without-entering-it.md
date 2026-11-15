---
title: "except RecursionError 的单测在 CPython 3.12 上是假绿：5000 层嵌套 JSON 不再抛"
domain: "testing"
tags:
  - "testing"
  - "cpython"
  - "json"
  - "false-green"
status: "published"
evidence_level: "E1"
created: "2026-11-15"
updated: "2026-11-15"
source: "intake-4933"
summary_plain: "拿深层嵌套 JSON 触发 RecursionError 的单测，在 CPython 3.12 上根本进不了 except 分支却照样通过；只有 3.11 上真的测到了守卫。"
trigger: "except RecursionError 的测试在 3.12 上通过得蹊跷：断言的还是兜底值"
verify: "3.11.14 对 5000 层嵌套抛 RecursionError，3.12.3 不抛（limit=100 也不抛）；改成 monkeypatch json.loads 抛后两版都进分支。"
provenance:
  issue: "#4933"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

A unit test that feeds deeply nested JSON to code with an `except RecursionError` guard silently exercises the success path on CPython 3.12: the test still asserts the fallback value, so it passes without ever entering the guarded branch. The same test fails (correctly exercising the guard) on CPython 3.11.

## Root Cause

CPython 3.11 raises `RecursionError` for `json.loads("[" * 5000 + "]" * 5000)` because the C decoder checks Python recursion. CPython 3.12 parses the same input successfully even with `sys.setrecursionlimit(100)` — deep JSON nesting no longer maps to Python recursion in 3.12. Source-identical guard tests therefore have interpreter-dependent coverage.

## Fix

Do not rely on deeply nested JSON to trigger `RecursionError` in tests. Raise it deterministically by patching the decoder actually used by the code under test (monkeypatch the module's `json.loads` to raise `RecursionError`) while keeping the stored value realistic, or parametrize/skip by interpreter version. When a guard test asserts only the fallback result, add an assertion or patch that proves the guarded branch was taken.

## Verification

Verified 2026-11 on Linux: CPython 3.11.14 raises `RecursionError` for 5000-level nested JSON in `json.loads`, while CPython 3.12.3 parses it successfully (also at recursion limit 100). After switching the test to a patched `json.loads` that raises, the guard is exercised on both interpreters. Re-check per Python version, since json decoder implementation details are not part of the documented contract.
