---
title: "MAMapType.naviNight 挂在普通 MAMapView 上白屏，只剩左下角 logo"
domain: "mobile"
tags:
  - "amap"
  - "ios"
  - "mkmapview"
  - "maptype"
  - "blank-screen"
  - "enum-misuse"
status: "published"
evidence_level: "E1"
created: "2026-11-02"
updated: "2026-11-02"
source: "intake-4146"
summary_plain: "夜间模式下整块地图纯黑，只剩左下角高德 logo，看起来像没网或 key 失效。"
trigger: "MAMapType.naviNight 挂在普通 MAMapView 上白屏，只剩左下角 logo. 夜间模式下整块地图纯黑，只剩左下角高德 logo，看起来像没网或 key 失效。"
verify: "夜间样式下瓦片正常显示；把枚举改回 .naviNight 能稳定复现纯黑，说明是枚举选错而不是网络/鉴权问题。"
provenance:
  issue: "#4146"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

夜间模式下整块地图纯黑，只剩左下角高德 logo，看起来像没网或 key 失效。

## Root Cause

MAMapType.naviNight 是「导航夜间视图」专用的枚举值，只给 AMapNavi 系列视图用；普通 MAMapView 拿它渲染不出瓦片，于是纯黑。Xcode 的 renamed/deprecated 提示只保证能编译，不保证语义正确。

## Fix

普通地图夜间模式用 `.standardNight`；只有真正嵌在导航视图里的地图才考虑 naviNight。

## Verification

夜间样式下瓦片正常显示；把枚举改回 .naviNight 能稳定复现纯黑，说明是枚举选错而不是网络/鉴权问题。
