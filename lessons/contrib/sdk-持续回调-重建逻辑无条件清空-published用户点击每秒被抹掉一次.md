---
title: "SDK 持续回调 + 重建逻辑无条件清空 @Published：用户点击每秒被抹掉一次"
domain: "mobile"
tags:
  - "amap"
  - "ios"
  - "idempotent"
  - "published-state"
  - "sdk-callback"
  - "state-reset"
status: "published"
evidence_level: "E1"
created: "2026-10-31"
updated: "2026-10-31"
source: "intake-4143"
summary_plain: "点方案按钮没反应——不高亮、其他线还在、像根本没点过。但代码里明明设了 selectedRouteID。"
trigger: "SDK 持续回调 + 重建逻辑无条件清空 @Published：用户点击每秒被抹掉一次. 点方案按钮没反应——不高亮、其他线还在、像根本没点过。但代码里明明设了 selectedRouteID。"
verify: "点方案后保持 10 秒不被重置；日志里 collectRouteOptions 的「跳过」计数 > 0；切方案时高亮与线样式同步变化。"
provenance:
  issue: "#4143"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

点方案按钮没反应——不高亮、其他线还在、像根本没点过。但代码里明明设了 selectedRouteID。

## Root Cause

高德会持续回调 rideManager(_:update:) → applyRoute → collectRouteOptions，而 collectRouteOptions 开头无条件执行 `routeOptions = []; awaitingPick = false; selectedRouteID = nil`。等于把用户刚做的选择每秒抹掉一次，视图看起来毫无反应。

## Fix

让重建逻辑幂等：

```swift
// collectRouteOptions：集合没变且已在等待选择 → 直接返回
let ids = Set(newOptions.map(\.id))
if awaitingPick && ids == Set(routeOptions.map(\.id)) { return }
```

applyRoute 在 awaitingPick 期间不要动 route。通用规则：凡是「用户交互写入的 @Published 状态」+「SDK 定时回调里重建数据」，重建必须幂等，不能无条件清空。

## Verification

点方案后保持 10 秒不被重置；日志里 collectRouteOptions 的「跳过」计数 > 0；切方案时高亮与线样式同步变化。
