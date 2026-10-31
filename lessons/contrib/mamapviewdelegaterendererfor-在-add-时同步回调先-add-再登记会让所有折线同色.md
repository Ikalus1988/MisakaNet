---
title: "MAMapViewDelegate.rendererFor 在 add() 时同步回调：先 add 再登记会让所有折线同色"
domain: "mobile"
tags:
  - "amap"
  - "ios"
  - "mkmapview"
  - "overlay"
  - "renderer"
  - "synchronous-callback"
status: "published"
evidence_level: "E1"
created: "2026-10-31"
updated: "2026-10-31"
source: "intake-4142"
summary_plain: "多方案预览时三条路线全是同一种蓝色，完全分不出哪条是哪条；点选高亮也看不出变化。"
trigger: "MAMapViewDelegate.rendererFor 在 add() 时同步回调：先 add 再登记会让所有折线同色. 多方案预览时三条路线全是同一种蓝色，完全分不出哪条是哪条；点选高亮也看不出变化。"
verify: "三条方案显示三种颜色/线宽；在 rendererFor 里打日志，确认回调与 add 在同一个调用栈内（同步），并且 index 不是 -1。"
provenance:
  issue: "#4142"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

多方案预览时三条路线全是同一种蓝色，完全分不出哪条是哪条；点选高亮也看不出变化。

## Root Cause

rendererFor 不是延迟回调，而是在 `map.add(overlay)` 的那一刻同步调用。代码写成「先 map.add(line)、再 altLines.append(line)」，回调发生时数组还是空的，index 取不到 → 全部落到 else 的默认样式分支。

## Fix

顺序必须是「先登记、再 add」：

```swift
altLines.append(line)   // 先登记，rendererFor 里才查得到 index
map.add(line)           // 再 add
```

重建折线时同理：先把新数组整体准备好，再逐条 add，最后统一 remove 旧的。

## Verification

三条方案显示三种颜色/线宽；在 rendererFor 里打日志，确认回调与 add 在同一个调用栈内（同步），并且 index 不是 -1。
