---
title: "抓拍点自动同步：接口只给版本号不给条数，且「版本没变」时没推进 lastSyncAt 导致每小时打一次"
domain: "nodejs"
tags:
  - "nodejs"
  - "sync"
  - "scheduler"
  - "version-check"
  - "timestamp"
  - "idempotent"
status: "published"
evidence_level: "E1"
created: "2026-10-31"
updated: "2026-10-31"
source: "intake-4163"
summary_plain: "1) 想做「不下载就知道要不要同步」在协议层面做不到；2) 调度器每小时都在打接口，明明上次刚查过，日志里反复「距上次同步 73 小时」。"
trigger: "抓拍点自动同步：接口只给版本号不给条数，且「版本没变」时没推进 lastSyncAt 导致每小时打一次. 1) 想做「不下载就知道要不要同步」在协议层面做不到；2) 调度器每小时都在打接口，明明上次刚查过，日志里反复「距上次同步 73 小时」。"
verify: "连续观察 24 小时：每小时一次的重复请求消失；版本变化时能同步且条数一致；内容相同时数据文件 mtime 不变（没写盘）。"
provenance:
  issue: "#4163"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

1) 想做「不下载就知道要不要同步」在协议层面做不到；2) 调度器每小时都在打接口，明明上次刚查过，日志里反复「距上次同步 73 小时」。

## Root Cause

1) `<PATH> 只返回 `{"version":"[REDACTED:card_number]"}`，条数必须把 1.2MB 密文拉下来解密才知道，版本号里不含条数信息。
2) 版本没变时代码只更新了 `lastCheckAt`，而调度器判定的依据是 `lastSyncAt`，于是下一次又算出「距上次 73 小时」→ 每小时再打一次接口。

## Fix

1) 做成两级判断：版本号没变 → 不下载；变了 → 拉下来比「条数 + 内容哈希」，两者都一样就**不写盘**，只更新版本号。
2) 版本没变时也要把 `lastSyncAt` 推到当前时间（数据确实是最新的），别只更新 `lastCheckAt`。

判据：调度器读哪个字段，就必须推进哪个字段，两个时间戳不能混用。

## Verification

连续观察 24 小时：每小时一次的重复请求消失；版本变化时能同步且条数一致；内容相同时数据文件 mtime 不变（没写盘）。
