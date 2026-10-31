---
title: "高德 iOS SDK showGreyAfterPass 默认 NO：已走路段不置灰，看起来像「导航没启动」"
domain: "mobile"
tags:
  - "amap"
  - "ios"
  - "navigation"
  - "polyline"
  - "renderer"
  - "default-no"
  - "silent-failure"
status: "published"
evidence_level: "E1"
created: "2026-10-31"
updated: "2026-10-31"
source: "intake-4139"
summary_plain: "进入导航模式后，车标在蓝线上滑动、转向卡也在动，但「走过的路」和「没走的路」颜色完全一样，没有已走/未走区分。因为转向卡在动，很容易误判成「导航没真正启动」或「算路失败」，先去排查导航引擎，方向就偏了。"
trigger: "高德 iOS SDK showGreyAfterPass 默认 NO：已走路段不置灰，看起来像「导航没启动」. 进入导航模式后，车标在蓝线上滑动、转向卡也在动，但「走过的路」和「没走的路」颜色完全一样，没有已走/未走区分。因为转向卡在动，很容易误判成「导航没真正启动」或「算路失败」，先去排…"
verify: "真机导航骑出 200 米以上：已走段变灰、未走段保持原色。若整条线仍同色，先确认设置的对象是 AMapNaviRideView 实例（不是内嵌的 MAMapView），再确认属性没被后续重建覆盖。"
provenance:
  issue: "#4139"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

进入导航模式后，车标在蓝线上滑动、转向卡也在动，但「走过的路」和「没走的路」颜色完全一样，没有已走/未走区分。因为转向卡在动，很容易误判成「导航没真正启动」或「算路失败」，先去排查导航引擎，方向就偏了。

## Root Cause

AMapNaviRideView 的 showGreyAfterPass 默认值是 NO（since 7.4.0），头文件注释只写了「走过的路线是否置灰,默认为NO」，没有任何文档提示。这个开关挂在导航视图 AMapNaviRideView 上，不在 MAMapView 或 naviManager 上，所以翻普通地图的头文件永远找不到它。命中的典型特征：导航确实在跑（转向卡在动、里程在涨），只是缺置灰效果。

## Fix

在 SwiftUI 的 makeUIView 里建好 AMapNaviRideView 之后立刻打开：

```swift
v.showGreyAfterPass = true   // ⚠️ 默认 NO，不设就永远不置灰
v.autoZoomMapLevel  = true   // 顺带开，导航视角更自然
```

不要指望「晚点再设」——导航视图一旦开始渲染就会按当前属性出图，早设省一次抖动。

## Verification

真机导航骑出 200 米以上：已走段变灰、未走段保持原色。若整条线仍同色，先确认设置的对象是 AMapNaviRideView 实例（不是内嵌的 MAMapView），再确认属性没被后续重建覆盖。
