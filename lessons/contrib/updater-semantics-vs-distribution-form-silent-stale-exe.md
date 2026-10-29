---
domain: "development"
title: "An auto-updater that speaks installer semantics silently never updates the portable exe users actually run"
tags:
  - "desktop"
  - "updater"
  - "installer"
  - "portable"
  - "silent-stale"
  - "tauri"
status: "draft"
created: "2026-10-28"
updated: "2026-10-28"
summary_plain: "产品同时发安装包和绿色版，更新器只按安装器语义工作——用户日常跑的绿色 exe 从来不会被更新，而「有新版/已更新」照常提示。"
trigger: "提示『有新版』→ 点更新 → 进度走完 → 桌面上那个 exe 仍旧版；直到某个『已修』的 bug 还在才发现"
verify: "更新后对比桌面 exe 的哈希/文件版本与安装目录里那份；不一致即复现"
evidence_level: "E1"
evidence_refs:
  - "issue:#3923"
provenance:
  source: "MCP intake question #3923 (claude-code), root cause supplied in the report"
  contributor: "zsxh1990"
  evidence: "root cause and reproduction steps taken from the issue report; **not independently reproduced** — no Windows host and no copy of the product were available. The mechanism (updater targets an install location; the portable exe lives elsewhere) is the report's claim, checked for internal consistency only."
---

# An auto-updater that speaks installer semantics silently never updates the portable exe users actually run

## Problem

The product ships **two distribution forms**:

- an **installer** (NSIS/MSI) — run once, launch from a shortcut
- a **portable green build** — a single exe, copy it anywhere, double-click

Documentation says daily use is the portable exe. The application ships **auto-update**.
Users read "has auto-update" and conclude their copy stays current. It does not:

> 提示「有新版」→ 点「立即更新」→ 进度条走完 → **桌面上那个 exe 还是旧的**

The failure is silent in both directions: the update reports success, and the stale exe
behaves exactly like the old version, so nothing looks wrong until a bug that was
announced as fixed is still present.

## Root Cause

**The updater's install semantics do not match the distribution form.**

Desktop app updaters (Tauri, Electron-updater, Squirrel and friends) target a *location*
— the install directory — and update the file they find there. That is correct for the
installer form. For the portable exe, the file being run is not in the install directory;
it is wherever the user copied it. The updater writes a new copy somewhere the user is not
running from, reports success, and the running exe is untouched.

Compounding it: the project documents "daily use is the portable exe", so the form the
updater *does* serve is precisely the one users are told not to use.

## Solution

Two fixes, and the second matters as much as the first.

1. **Match the update mechanism to the form.** Either make the portable form self-updating
   in place (replace the running exe's file, with the usual Windows caveats about
   renaming the running image rather than overwriting it), or **hide/disable auto-update
   entirely in the portable build**. Shipping an updater that cannot reach the file the
   user runs is worse than shipping none: it converts "out of date" from an observable
   fact into a false reassurance.

2. **Make the update report name what it updated.** "Update complete" should say *which
   path* now holds the new version. Then the user can see it wrote somewhere else. A
   progress bar that does not name its target cannot be checked.

## Verification

**Not reproduced.** The root cause above is the report's, and it is internally consistent —
an updater keyed to an install location cannot modify a copy living elsewhere. But no
Windows host and no copy of the product were available here, so the specific sequence
(提示→更新→仍旧版) was not executed.

What *is* verifiable cheaply by whoever has the product:

```bash
# 更新前后各跑一次，比对用户实际启动的那个 exe
shasum ~/Desktop/theapp.exe        # 更新前
# …点「立即更新」…
shasum ~/Desktop/theapp.exe        # 更新后 —— 哈希不变即复现
```

## Note

The general shape: **a feature can be present, working, and pointed at the wrong object.**
Auto-update was not broken; it was updating something the user was not running. The
category is "the mechanism and the subject are not the same thing", and it hides because
every individual step reports success.

The diagnostic that separates it from a real update failure is the one above: compare the
file the user actually runs, not the one the updater logs about.
