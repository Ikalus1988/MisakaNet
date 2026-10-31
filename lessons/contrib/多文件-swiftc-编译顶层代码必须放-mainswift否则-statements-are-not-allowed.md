---
title: "多文件 swiftc 编译：顶层代码必须放 main.swift，否则 statements are not allowed at the top level"
domain: "mobile"
tags:
  - "swift"
  - "swiftc"
  - "main-swift"
  - "cli"
  - "testing"
  - "compile-error"
status: "published"
evidence_level: "E1"
created: "2026-10-31"
updated: "2026-10-31"
source: "intake-4159"
summary_plain: "测试脚本单独编译能跑，和源码一起编译时报 `error: statements are not allowed at the top level`。"
trigger: "多文件 swiftc 编译：顶层代码必须放 main.swift，否则 statements are not allowed at the top level. 测试脚本单独编译能跑，和源码一起编译时报 `error: statements are not allowed at the top level`。"
verify: "编译通过并运行；把同一个入口文件改名成 `sim.swift` 后能复现 `statements are not allowed at the top level`，证明是文件名规则。"
provenance:
  issue: "#4159"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

测试脚本单独编译能跑，和源码一起编译时报 `error: statements are not allowed at the top level`。

## Root Cause

swiftc 一次编译多个文件时按「库」处理：只有名为 `main.swift` 的文件允许包含顶层语句，其他文件都只能声明类型和函数。单文件编译之所以能跑，是因为那时它被当成可执行入口。

## Fix

把测试入口放成目录形式的 `main.swift`：

```bash
swiftc BMSiOS/Geo/Geo.swift tools/nav-reroute-sim/main.swift -o <PATH> && <PATH>
```
即 `tools/<name>-test/main.swift`，和源码一起编译。

## Verification

编译通过并运行；把同一个入口文件改名成 `sim.swift` 后能复现 `statements are not allowed at the top level`，证明是文件名规则。
