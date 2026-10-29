---
domain: "development"
title: "A CWD-relative tool lookup passes every test and fails for every user: the test harness starts the app from the repo"
tags:
  - "desktop"
  - "cwd"
  - "path-resolution"
  - "false-green"
  - "swallowed-exception"
  - "test-environment"
status: "draft"
created: "2026-10-28"
updated: "2026-10-28"
summary_plain: "小工具用 CWD 相对路径查找，测试从仓库目录拉起应用刚好命中，用户从桌面快捷方式启动就落空；加上 catch 返回 null，整列静默 N/A、零报错。"
trigger: "开发机 UI 冒烟 8/8 全绿，真实用户启动后整列 N/A，无任何错误"
verify: "把测试的启动 CWD 换成系统临时目录再跑——同一功能立刻红，即复现"
evidence_level: "E1"
evidence_refs:
  - "issue:#3962"
provenance:
  source: "MCP intake issue #3962 (claude-code), root cause supplied in the report"
  contributor: "zsxh1990"
  evidence: "root cause and fix suggestions taken from the issue report; **not independently reproduced** — no copy of the application was available. The mechanism (CWD-relative lookup + swallowed exception + test harness started from repo root) is the report's claim, checked for internal consistency only. The proposed verification — run the tests with a neutral CWD — is offered as the cheap reproduction for whoever has the codebase."
---

# A CWD-relative tool lookup passes every test and fails for every user: the test harness starts the app from the repo

## Problem

A desktop feature is green on the development machine — UI smoke 8/8 — and renders an
**entire column of silent `N/A`** for real users, with zero errors. Tests pass. The engine
passes. Golden-file comparison passes. Only the real launch form fails.

## Root Cause

Three things, and each alone would have been survivable:

1. **The lookup is CWD-relative.** The app calls an external helper (a binary converter,
   tens of KB) found at `./bin/tool.exe`, with a fallback to an install path that does not
   exist on the machine.

2. **The tests start the app from the repo directory.** `./bin/tool.exe` resolves against
   the CWD, which in tests happens to be the repo root — where `bin/` lives. Every test
   hits it. That is not coverage; that is an accident of the working directory.

3. **The failure is swallowed.** `catch { return null }` turns "could not find the tool"
   into `null`, and `null` renders as `N/A`. No log, no error, no distinction between
   "not applicable" and "could not run".

Users launch from a desktop shortcut, where CWD is the desktop or a system directory.
The lookup misses, the exception is swallowed, and the column is empty. The same feature,
the same binary, two working directories, two outcomes — and the one where it works is
the only one anyone tested.

## Solution

Three fixes; the third is the one that stops the class.

1. **Remove the CWD dependency.** Embed the helper in the binary (`include_bytes!`, tens of
   KB is not a cost) and extract to a temp directory at runtime; keep an external copy
   first on the search path for overrides. From then on the result does not depend on how
   the app was launched.

2. **Make `N/A` carry a reason.** Every `return null` becomes
   `{ verdict: 'N/A', detail: <why> }`, and the reason is shown. A silent `N/A` is
   indistinguishable from a genuine "nothing to show"; those are opposite facts and must
   not share a rendering.

3. **Start tests with a neutral CWD** (a system temp directory) — never the repo root.
   This is the fix that generalises: any test that launches the process from the directory
   containing its own fixtures is testing the fixtures, not the lookup.

## Verification

**Not reproduced** — no copy of the application was available. The root cause is the
report's; it is internally consistent and the proposed fix matches it exactly.

The cheap reproduction for anyone with the codebase:

```bash
cd "$(mktemp -d)" && <run the same UI smoke suite>
# 同一批用例立刻红 —— 那就是 CWD 在撑着它们
```

If the suite stays green from a neutral CWD, the lookup is already CWD-independent and
this diagnosis does not apply.

## Note

The general shape is **"green because of where the test ran"**, and it is worth naming
because it survives every form of test quality discipline. The tests were not wrong, the
assertions were not weak, and the code path was genuinely exercised — the *environment*
was doing the work.

The signature to grep for: a test that passes from the repo root and fails from anywhere
else is measuring the CWD. Same family as the "test environment ≠ production environment"
class, but sharper, because here the fix is one line of test setup.
