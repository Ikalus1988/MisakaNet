---
title: "AMapNaviRideView.showMode 被拖图改掉后不会自动恢复，镜头停在原处"
domain: "mobile"
tags:
  - "amap"
  - "ios"
  - "showmode"
  - "camera"
  - "user-gesture"
  - "restore-state"
status: "published"
evidence_level: "E1"
created: "2026-10-31"
updated: "2026-10-31"
source: "intake-4144"
summary_plain: "导航时拖了一下地图，之后车骑出去几百米，镜头还停在他乡，必须手动点定位才回来。"
trigger: "AMapNaviRideView.showMode 被拖图改掉后不会自动恢复，镜头停在原处. 导航时拖了一下地图，之后车骑出去几百米，镜头还停在他乡，必须手动点定位才回来。"
verify: "拖图后正常骑行 3 秒，镜头自动回到车标；静止状态下拖图不会被强行拉回（不会跟用户抢操作）。"
provenance:
  issue: "#4144"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

导航时拖了一下地图，之后车骑出去几百米，镜头还停在他乡，必须手动点定位才回来。

## Root Cause

AMapNaviRideView.showMode 默认是 .carPositionLocked（锁车跟随）。用户一拖动，SDK 把它切成 .normal，之后不会自己切回来；而「显示模式变化」的回调并不保证每次都来，靠回调恢复不可靠。

## Fix

主动轮询 + 条件恢复：
- 每帧读 v.showMode 判断是否被拖走，不依赖回调；
- 速度 ≥5 km/h 持续 3 秒 → 设回 .carPositionLocked；
- 「定位」按钮 → 立刻设回；
- 刚拉回的 1.5 秒内不再判定，防止 SDK 属性滞后导致反复触发。

## Verification

拖图后正常骑行 3 秒，镜头自动回到车标；静止状态下拖图不会被强行拉回（不会跟用户抢操作）。
