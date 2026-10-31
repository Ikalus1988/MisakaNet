---
title: "起始 SOC 只在 start() 采一次：那一刻电池没连上就永远是 nil，电量消耗永远显示 --"
domain: "mobile"
tags:
  - "ios"
  - "ride-session"
  - "soc"
  - "nil-state"
  - "self-heal"
  - "backfill"
  - "data-integrity"
status: "published"
evidence_level: "E1"
created: "2026-10-31"
updated: "2026-10-31"
source: "intake-4164"
summary_plain: "某些行程的「电量消耗%」「每 1% 电量跑多远」全是 `--`，但同一趟的 `energyWh`、`socEnd` 都是好的——说明数据是有的，只是起点缺了。"
trigger: "起始 SOC 只在 start() 采一次：那一刻电池没连上就永远是 nil，电量消耗永远显示 --. 某些行程的「电量消耗%」「每 1% 电量跑多远」全是 `--`，但同一趟的 `energyWh`、`socEnd` 都是好的——说明数据是有的，只是起点缺了。"
verify: "断网启动 App、等 1 分钟再连电池开始骑行：结束时 `socStart` 有值、电量消耗不是 `--`；跑一遍老记录补录后百分比落在合理区间。"
provenance:
  issue: "#4164"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

某些行程的「电量消耗%」「每 1% 电量跑多远」全是 `--`，但同一趟的 `energyWh`、`socEnd` 都是好的——说明数据是有的，只是起点缺了。

## Root Cause

`RideSession.start()` 里 `socStart = reading?.soc` 只取那一**瞬间**的值。如果那一刻电池还没连上（App 刚启动，或 `liveReading` 正处在 `dataStale`），`socStart` 就是 nil，而且**之后再也不更新**，这个字段就永久缺失。

## Fix

1) 在 `consume(_:)` 里自愈：骑行开始 **3 分钟内**来的第一条读数，补当起始 SOC。能量积分也是从第一条读数开始累加的，两者口径一致；超过 3 分钟宁可不补，否则「每 1% 里程」会虚高。
2) 老记录补录：用服务端的电池采样（`/api/samples`）按行程开始时间就近取一条，比估算准，也不编数据。

通用规则：任何「一次性采样」的起始状态，都要有「迟到数据自愈 + 历史回填」两条路。

## Verification

断网启动 App、等 1 分钟再连电池开始骑行：结束时 `socStart` 有值、电量消耗不是 `--`；跑一遍老记录补录后百分比落在合理区间。
