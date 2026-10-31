---
title: "高德导航 addDataRepresentative 不补发历史事件：晚创建的视图拿不到路线和定位"
domain: "mobile"
tags:
  - "amap"
  - "ios"
  - "delegate"
  - "late-registration"
  - "replay-state"
  - "swiftui"
status: "published"
evidence_level: "E1"
created: "2026-10-31"
updated: "2026-10-31"
source: "intake-4140"
summary_plain: "导航图面上没有路线、没有进度，但转向卡在动；或者反过来，路线有、转向卡不动。两个症状都出现过，容易以为 SDK 回调挂了。"
trigger: "高德导航 addDataRepresentative 不补发历史事件：晚创建的视图拿不到路线和定位. 导航图面上没有路线、没有进度，但转向卡在动；或者反过来，路线有、转向卡不动。两个症状都出现过，容易以为 SDK 回调挂了。"
verify: "从「选路线 → 开始导航」进入，第一帧就能看到完整路线与进度；杀进程后直接冷启动进导航页，也复现不出空白路线。"
provenance:
  issue: "#4140"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

导航图面上没有路线、没有进度，但转向卡在动；或者反过来，路线有、转向卡不动。两个症状都出现过，容易以为 SDK 回调挂了。

## Root Cause

导航视图是在「进入导航之后」才被 SwiftUI 创建的（条件渲染），而算路回调 rideManager(_:update naviRoute:) 在那之前就已经发过了。addDataRepresentative 只订阅注册之后的事件，不会补发历史事件，于是视图永远等不到那条路线。

## Fix

注册完立刻把当前状态补推一次，定位也补喂一次：

```swift
m.addDataRepresentative(v as AMapNaviRideDataRepresentable)
if let r = m.naviRoute { v.rideManager(m, update: r) }   // 补推路线
if let loc = lastKnown { v.setExternalLocation(loc) }   // 补喂定位
```

同类问题适用于任何「晚注册的 delegate」：注册后要把已有的最新状态重放一遍。

## Verification

从「选路线 → 开始导航」进入，第一帧就能看到完整路线与进度；杀进程后直接冷启动进导航页，也复现不出空白路线。
