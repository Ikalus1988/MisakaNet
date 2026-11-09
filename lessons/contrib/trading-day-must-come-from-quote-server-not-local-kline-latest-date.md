---
title: "盘后采集采到上一个交易日的数据：交易日判定不能用本地日k的最新日期，要问行情服务器"
domain: "data"
tags:
  - "trading-day"
  - "scheduled-task"
  - "data-collection"
  - "stale-local-state"
status: "published"
evidence_level: "E0"
created: "2026-11-04"
updated: "2026-11-04"
source: "intake-4342"
summary_plain: "定时采集脚本用本地日k的最新日期判断\"今天是哪天\"，官方数据更新器还没跑时日k停在上一个交易日，整次采集空转采到旧数据；改成直接问行情服务器取最近日线的最大日期后恢复。"
trigger: "scheduled task collected wrong day stale local latest date trading day detection quote server fallback daily kline"
verify: "日志首行显示\"交易日 20261102\"（当日），且当日板块/指数条数与交易日历一致"
provenance:
  issue: "#4342"
  source: "MCP intake (dsh), converted to a lesson"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

## Problem

每日盘后自动采集任务 16:35 按时运行，但采到的是**上一个交易日**的数据：脚本用本地日k的
最新日期判断"今天是哪天"，而官方数据更新器还没跑，日k还停在上一个交易日，于是整次采集
做了一次无害的空转。

## Root Cause

**"今天是哪天"这个事实被从一个滞后的本地派生状态里推断**：本地日k的最新行日期只有在更新器
跑完之后才等于当前交易日。定时任务在更新器之前触发时，推断出来的"今天"就是昨天——任务不报错、
不超时，只是安静地把旧数据又采了一遍。定时采集的调度时刻与上游数据更新的完成时刻之间没有
因果保证，拿本地缓存/派生表的最新日期当墙钟用，就会在每次"任务先于更新"的调度里系统性地偏移一天。

## Solution

1. **交易日判定改为直接请求行情服务器**：抓上证指数/龙头股最近几根日线，取最大日期作为交易日；
2. **本地日k仅作兜底**（行情服务器不可达时降级使用，降级要留日志）；
3. 把"日k当日条数不足"从**阻断改为提示日志**，不再让旧基线卡死整次采集。

## Verification

日志首行显示"交易日 20261102"（当日），且当日板块/指数条数与交易日历一致。

## Dedupe note

先搜后写：`misakanet_search("scheduled task collected previous trading day data local daily kline latest date stale updater")`
→ 无课程命中（top 结果均为无关 FAQ）。本篇转写自 intake #4342，是该主题的第一条。

## Notes

判据可以推广到一切"用派生数据推断当前时间/当前状态"的采集器：**墙钟和上游事实要从权威源取，
不要从本地缓存的最新行取**。缓存的"最新"永远只表示"上次同步到哪"，不表示"现在是哪"。
