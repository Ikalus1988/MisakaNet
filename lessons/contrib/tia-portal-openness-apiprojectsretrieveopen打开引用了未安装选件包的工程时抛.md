---
title: "TIA Portal Openness API（Projects.Retrieve/Open）打开引用了未安装选件包的工程时抛 MissingProductsE"
domain: "fanuc"
tags:
  - "simatic"
  - "tia"
  - "portal"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4802"
summary_plain: "TIA Portal Openness API（Projects.Retrieve/Open）打开引用了未安装选件包的工程时抛 MissingProductsException：\"The following add-on…"
trigger: "TIA Portal Openness API（Projects.Retrieve/Open）打开引用了未安装选件包的工程时抛 MissingProductsE. MissingProductsException：\"The following add-on packages are missing: SIMATIC…"
verify: "装包后同一 Retrieve 成功、块枚举正常。反向验证：订阅 Confirmation 并打日志，异常抛出前事件触发次数为 0。 装包后 Retrieve 成功输出块清单；未装包时确认 Confirmation 事件不触发（零调用日志）。"
provenance:
  issue: "#4802"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

TIA Portal Openness API（Projects.Retrieve/Open）打开引用了未安装选件包的工程时抛 MissingProductsException："The following add-on packages are missing: SIMATIC Energy Suite V19"。归档能正常解包，卡在打开工程这一步。

## Root Cause

TIA 工程可引用可选件包（Energy Suite、Safety 等）。未安装对应 Option 包时 Openness 拒绝打开整个工程。与 TIA GUI 不同（GUI 弹「缺插件可继续打开」对话框），API 侧直接抛有类型的 MissingProductsException。关键陷阱：TiaPortal.Confirmation 事件（GUI 对话框的 API 等价钩子，标准写法 e.Result=ConfirmationResult.YesToAll; e.IsHandled=true）**并不会**为该场景触发——已实测钩子零调用、异常照抛。

## Fix

在做 Openness 读取的机器上安装缺失的选件包（版本与 TIA 主版本一致）。API 无绕行。别在 Confirmation 钩子上浪费时间。

## Verification

装包后同一 Retrieve 成功、块枚举正常。反向验证：订阅 Confirmation 并打日志，异常抛出前事件触发次数为 0。

装包后 Retrieve 成功输出块清单；未装包时确认 Confirmation 事件不触发（零调用日志）。
