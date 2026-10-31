---
title: "NAS → Trip 手工映射漏字段（movingMs）：从 NAS 恢复的行程「骑行均速」永远是 --"
domain: "mobile"
tags:
  - "ios"
  - "persistence"
  - "json-mapping"
  - "optional-field"
  - "data-integrity"
  - "movingms"
status: "published"
evidence_level: "E1"
created: "2026-10-31"
updated: "2026-10-31"
source: "intake-4166"
summary_plain: "从 NAS 恢复的行程，「骑行均速」显示 `--`；路线耗时的加权平均也算不进这些记录。本地记录的同一趟是正常的。"
trigger: "NAS → Trip 手工映射漏字段（movingMs）：从 NAS 恢复的行程「骑行均速」永远是 --. 从 NAS 恢复的行程，「骑行均速」显示 `--`；路线耗时的加权平均也算不进这些记录。本地记录的同一趟是正常的。"
verify: "从 NAS 恢复一条行程：均速不是 `--`，且恢复前后的 Trip 逐字段一致；写个脚本对比 `Trip` 的所有 key 与 `trip(from:)` 的映射覆盖率（缺一个就报错）。"
provenance:
  issue: "#4166"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

从 NAS 恢复的行程，「骑行均速」显示 `--`；路线耗时的加权平均也算不进这些记录。本地记录的同一趟是正常的。

## Root Cause

`TripStore.trip(from:)` 逐字段手工映射 NAS 返回的 JSON，漏了 `movingMs`。新增字段时极易漏，编译器也不会提醒——构造参数都是可选的，漏了就是 nil。

## Fix

补上 `movingMs`（并补 `deviceId`，补录采样要用）。把「记录字段清单」做成对照表，三份序列化一起改：

`UplinkRide` 加字段 → 服务端落盘白名单 → `TripStore.trip(from:)` 映射 → `Trip` 加 Optional 字段 → 需要跨重启的统计再进 `RideSessionSnapshot`。

## Verification

从 NAS 恢复一条行程：均速不是 `--`，且恢复前后的 Trip 逐字段一致；写个脚本对比 `Trip` 的所有 key 与 `trip(from:)` 的映射覆盖率（缺一个就报错）。
