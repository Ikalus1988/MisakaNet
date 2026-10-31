---
title: "进导航后相机跳到北京天安门：视图创建时还没有定位，lastKnown 只在导航中才赋值"
domain: "mobile"
tags:
  - "amap"
  - "ios"
  - "navigation"
  - "camera"
  - "view-lifecycle"
  - "last-known-location"
status: "published"
evidence_level: "E1"
created: "2026-10-31"
updated: "2026-10-31"
source: "intake-4169"
summary_plain: "选完路线点开始导航，地图直接跳到**北京天安门**（高德默认视野），必须点一次右下角定位才回到脚下。"
trigger: "进导航后相机跳到北京天安门：视图创建时还没有定位，lastKnown 只在导航中才赋值. 选完路线点开始导航，地图直接跳到**北京天安门**（高德默认视野），必须点一次右下角定位才回到脚下。"
verify: "冷启动直接进导航：第一帧就在当前位置，不出现天安门；静止不动 30 秒相机不漂；点定位按钮能立刻回到自身。"
provenance:
  issue: "#4169"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

选完路线点开始导航，地图直接跳到**北京天安门**（高德默认视野），必须点一次右下角定位才回到脚下。

## Root Cause

`AMapNaviRideView` 是在 `navigating` 变 true **之后**才被创建的，那一刻还没有新的 GPS 点；而 `NavService.lastKnown` 以前是 `guard navigating` **之后**才赋值 → 视图创建时拿到 nil，SDK 没有位置可锁，就停在自己的默认视野。

## Fix

三件事一起做：
1. `feed(location:)` 里**先记 `lastKnown`，再判断是否在导航**（任何时候都记）；
2. `attachRideView` → `seedViewLocation()`：有 `lastKnown` 就喂；没有就拿算路起点反算 WGS-84（`gcj02ToWgs84`）顶一下；0.8 秒后再补一次（视图刚进窗口时 `setExternalLocation` 可能还没生效）；
3. `syncCamera`：进导航头 5 秒每 0.7 秒「锁一次 + setCenter(自己)」，之后相机离人 > 2km 就再拉一次。

另外加 1Hz 看门狗定时器：停着不动时 `speed` / `coordinate` 都没变化，SwiftUI 可能一次都不回调 `updateUIView`，相机校正不能只靠它。

## Verification

冷启动直接进导航：第一帧就在当前位置，不出现天安门；静止不动 30 秒相机不漂；点定位按钮能立刻回到自身。
