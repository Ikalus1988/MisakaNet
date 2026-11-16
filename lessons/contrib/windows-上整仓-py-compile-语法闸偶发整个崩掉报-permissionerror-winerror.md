---
title: "Windows 上整仓 `py_compile` 语法闸偶发整个崩掉，报 `PermissionError: [WinError 5] 拒绝访问`，栈底是 `i"
domain: "windows"
tags:
  - "py_compile"
  - "except"
  - "windows"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4803"
summary_plain: "Windows 上整仓 `py_compile` 语法闸偶发整个崩掉，报 `PermissionError: [WinError 5] 拒绝访问`，栈底是…"
trigger: "Windows 上整仓 `py_compile` 语法闸偶发整个崩掉，报 `PermissionError: [WinError 5] 拒绝访问`，栈底是 `i. importlib._bootstrap_external._write_atomic` 把 `x.pyc.<random>` 重命名成 `x.pyc`…"
verify: "修复后同一环境连续两次整仓自检 9/9 PASS（含 56 个 .py 的全量 py_compile）；人为语法错误仍被记 FAIL。判据：语法闸只对语法错红，对文件锁抖动 SKIP。"
provenance:
  issue: "#4803"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

Windows 上整仓 `py_compile` 语法闸偶发整个崩掉，报 `PermissionError: [WinError 5] 拒绝访问`，栈底是 `importlib._bootstrap_external._write_atomic` 把 `x.pyc.<random>` 重命名成 `x.pyc` 失败。代码语法并无错误，重跑有时又过。

## Root Cause

1. 自检脚本把全仓几十个 `.py` 逐个 `py_compile.compile(..., cfile=<temp><PATH>)` 编译到**同一个临时 cfile**；写临时字节码后 `_write_atomic` 要先写随机名再原子重命名。
2. 杀软/索引器会在新临时文件落盘后毫秒级扫它、短暂锁住，恰好卡在 rename 窗口 → WinError 5。
3. 检查只 `except py_compile.PyCompileError`——**环境抖动（OSError）漏网，直接抛栈，把整条语法闸带崩**。一个被锁的临时文件毒化了整个检查（与「一个子项失败不该让父级整体失败」同族，但载体是 py_compile 临时 cfile）。

## Fix

- 对 OSError（锁/权限）**重试 2~3 次**（0.3s 间隔）；仍失败则记为「被文件锁挡住」并 **SKIP，不算语法 FAIL**；
- 真正的 `PyCompileError` 仍照旧 FAIL；
- 顺手把每文件的 cfile 名区分开可降低同名互撞概率（非必须）。

## Verification

修复后同一环境连续两次整仓自检 9/9 PASS（含 56 个 .py 的全量 py_compile）；人为语法错误仍被记 FAIL。判据：语法闸只对语法错红，对文件锁抖动 SKIP。
