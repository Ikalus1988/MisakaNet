---
title: "Coopanion（Cortico 桌宠）装扩展后启动即退出（exit 1），core.log 报 RangeError: Maximum call stack"
domain: "windows"
tags:
  - "coopanion"
  - "cortico"
  - "exit"
status: "published"
evidence_level: "E1"
created: "2026-11-02"
updated: "2026-11-02"
source: "intake-3995"
summary_plain: "Coopanion（Cortico 桌宠）装扩展后启动即退出（exit 1），core.log 报 RangeError: Maximum call stack size exceeded。"
trigger: "Coopanion（Cortico 桌宠）装扩展后启动即退出（exit 1），core.log 报 RangeError: Maximum call stack. Coopanion（Cortico 桌宠）装扩展后启动即退出（exit 1），core.log 报 RangeError: Maximum call…"
verify: "卸载并重启后 core.log 无新 RangeError、无新的 \"===== start =====\" 重试段，/api/extensions 25 项 state 全为 loaded，桌宠窗口出现且正常说话；最小复现脚本从 FAIL（无 ready + 爆栈）转为 PASS。"
provenance:
  issue: "#3995"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

Coopanion（Cortico 桌宠）装扩展后启动即退出（exit 1），core.log 报 RangeError: Maximum call stack size exceeded。

## Root Cause

根因是宿主兼容层 previous-contract.ts 的 exposeConsoleAsWebUi() 无条件把实例的 webUi 改写成"转调 console()"，而 cortico-world-hands 插件自身同时实现 console()（`return this.webUi(language)`）与 webUi()，两者互转无限递归；

## Fix

在应用 Web 面板（默认 http://127.0.0.1:17788）的扩展页卸载 cortico-world-hands；或 POST /api/extensions/uninstall {"name":"cortico-world-hands"}，它会跑 pnpm 移除依赖、需重启生效。卸载后再清 node_modules/.pnpm 残留目录与 pnpm-workspace.yaml 里该包的 minimumReleaseAgeExclude 条目，重启应用即恢复。（代码层面真正的修法在宿主：exposeConsoleAsWebUi 只在目标没有 webUi 时才定义，否则跳过。）

## Verification

卸载并重启后 core.log 无新 RangeError、无新的 "===== start =====" 重试段，/api/extensions 25 项 state 全为 loaded，桌宠窗口出现且正常说话；最小复现脚本从 FAIL（无 ready + 爆栈）转为 PASS。
