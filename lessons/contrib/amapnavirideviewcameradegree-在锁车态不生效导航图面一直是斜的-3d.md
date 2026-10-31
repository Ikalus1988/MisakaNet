---
title: "AMapNaviRideView.cameraDegree 在锁车态不生效：导航图面一直是斜的 3D"
domain: "mobile"
tags:
  - "amap"
  - "ios"
  - "navigation"
  - "camera"
  - "3d"
  - "kvc"
  - "private-view-hierarchy"
status: "published"
evidence_level: "E1"
created: "2026-10-31"
updated: "2026-10-31"
source: "intake-4168"
summary_plain: "导航时地图是「带角度的」3D，不是 2D 平面；`v.cameraDegree = 0` 设了完全没效果，也没有报错。"
trigger: "AMapNaviRideView.cameraDegree 在锁车态不生效：导航图面一直是斜的 3D. 导航时地图是「带角度的」3D，不是 2D 平面；`v.cameraDegree = 0` 设了完全没效果，也没有报错。"
verify: "导航中图面是 2D 平面；双指上滑不再变成 3D；转弯与锁车/解锁切换时没有抖动或闪烁。"
provenance:
  issue: "#4168"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

导航时地图是「带角度的」3D，不是 2D 平面；`v.cameraDegree = 0` 设了完全没效果，也没有报错。

## Root Cause

`AMapNaviRideView.h` 对 `cameraDegree` 的注释是「**非锁车状态下**地图 cameraDegree，**锁车态下内部会处理**，默认 35.0」。也就是说锁车时 SDK 自己按 35° 俯仰渲染，外部设的值压根没被使用。属性注释里的生效条件是最容易漏的信息。

## Fix

SDK 没公开 `mapView` 属性（只有 `mapViewDelegate`），但图面就是一个嵌进去的 `MAMapView` —— 递归子视图把它找出来直接压平：

```swift
static func findMapView(_ root: UIView) -> MAMapView? {
    if let m = root as? MAMapView { return m }
    for sub in root.subviews { if let m = findMapView(sub) { return m } }
    return nil
}
mv.cameraDegree = 0
mv.setCameraDegree(0, animated: false, duration: 0)
mv.isRotateCameraEnabled = false   // 双指上滑别再拉成 3D
```

WARNING: 别用 KVC `value(forKey: "mapView")` —— key 不存在会直接抛异常崩溃。
WARNING: 限流：0.3° 以内不动、0.5 秒最多写一次，避免和 SDK 的相机更新每帧互顶。

## Verification

导航中图面是 2D 平面；双指上滑不再变成 3D；转弯与锁车/解锁切换时没有抖动或闪烁。
