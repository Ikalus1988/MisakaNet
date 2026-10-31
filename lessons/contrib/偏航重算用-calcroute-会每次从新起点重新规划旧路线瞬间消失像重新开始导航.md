---
title: "偏航重算用 calcRoute 会「每次从新起点重新规划」：旧路线瞬间消失，像重新开始导航"
domain: "mobile"
tags:
  - "amap"
  - "ios"
  - "navigation"
  - "reroute"
  - "recalculate"
  - "route-clearing"
status: "published"
evidence_level: "E1"
created: "2026-10-31"
updated: "2026-10-31"
source: "intake-4167"
summary_plain: "骑错路口后路线要等好几秒才更新，新路线是从当前位置画一条**全新的**，原来的路线直接消失，体感像「重新开始导航」。"
trigger: "偏航重算用 calcRoute 会「每次从新起点重新规划」：旧路线瞬间消失，像重新开始导航. 骑错路口后路线要等好几秒才更新，新路线是从当前位置画一条**全新的**，原来的路线直接消失，体感像「重新开始导航」。"
verify: "骑错路口后旧路线不消失、新路线尽量并回原线，更新明显快于完整算路；日志里 `fallbackFullRecalc` 计数为 0。"
provenance:
  issue: "#4167"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

骑错路口后路线要等好几秒才更新，新路线是从当前位置画一条**全新的**，原来的路线直接消失，体感像「重新开始导航」。

## Root Cause

偏航时自己调了 `calcRoute(from: 当前位置, to: 终点)`——那是一次**完整的重新算路**：
- 第一行就把 `route = []` 清空 → 地图上旧路线立刻没了；
- 请求带的是新起点，高德返回的就是一条以新起点开头的路线；
- 还要重走一遍多方案、抓拍点匹配、自动开始导航那套流程 → 慢。

## Fix

改用 SDK 自带的导航中重算接口 `recalculateRideRoute()` / `recalculateEleBikeRoute()`（头文件原文：导航过程中重新规划路径，起点为当前位置，终点位置不变）：保留原路线上下文、只补「当前位置 → 原路线」这一段、不清空导航状态、请求轻量。

同时收紧偏航判定（这才是「慢」的主因）：偏出 50m 以上直接算、30~50m 要连续 2 个点、精度差于 35m 的点不参与判断、冷却 8→6s、6 秒没回调就放开「重新规划中」。

## Verification

骑错路口后旧路线不消失、新路线尽量并回原线，更新明显快于完整算路；日志里 `fallbackFullRecalc` 计数为 0。
