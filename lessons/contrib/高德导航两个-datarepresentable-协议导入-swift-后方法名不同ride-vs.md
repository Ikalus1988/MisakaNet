---
title: "高德导航两个 DataRepresentable 协议导入 Swift 后方法名不同（ride vs rideManager）"
domain: "mobile"
tags:
  - "amap"
  - "ios"
  - "objective-c-interop"
  - "protocol"
  - "selector"
  - "swift-import"
status: "published"
evidence_level: "E1"
created: "2026-10-31"
updated: "2026-10-31"
source: "intake-4141"
summary_plain: "编译报 `cannot convert AMapNaviRideManager to AMapNaviEleBikeManager`，或者 `has no member 'ride'`。明明 Objective-C…"
trigger: "高德导航两个 DataRepresentable 协议导入 Swift 后方法名不同（ride vs rideManager）. 编译报 `cannot convert AMapNaviRideManager to AMapNaviEleBikeManager`，或者 `has no member…"
verify: "两种导航模式都能编译通过且路线正常渲染；最小片段 `swiftc -typecheck -sdk $(xcrun --sdk iphoneos --show-sdk-path) -F Vendor` 无报错。"
provenance:
  issue: "#4141"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

编译报 `cannot convert AMapNaviRideManager to AMapNaviEleBikeManager`，或者 `has no member 'ride'`。明明 Objective-C 里两个协议的方法是同一个 selector，代码看起来完全对称。

## Root Cause

Objective-C 里两个协议的方法都叫 rideManager:updateNaviRoute:，但 Swift 导入时按协议上下文取了不同名字：AMapNaviEleBikeDataRepresentable → `ride(_:update:)`；AMapNaviRideDataRepresentable → `rideManager(_:update:)`。同名 ObjC selector 在不同协议里映射出不同 Swift 名，Xcode 的补全也帮不上忙。

## Fix

不要绕协议类型，直接调 AMapNaviRideView 上的方法：

```swift
case .eleBike: v.ride(m, update: r)
case .ride:    v.rideManager(m, update: r)
```

同类：AMapNaviRideViewDelegate 的「显示模式变化」回调 Swift 名是 `rideView(_:didChange:)`，不是 didChangeShowMode。拿不准时用 `swiftc -typecheck` 单独编译一个最小片段验证签名，比反复全量编译快得多。

## Verification

两种导航模式都能编译通过且路线正常渲染；最小片段 `swiftc -typecheck -sdk $(xcrun --sdk iphoneos --show-sdk-path) -F Vendor` 无报错。
