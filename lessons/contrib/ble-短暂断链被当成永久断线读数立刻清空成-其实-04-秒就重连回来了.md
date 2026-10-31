---
title: "BLE 短暂断链被当成永久断线：读数立刻清空成 --，其实 0.4 秒就重连回来了"
domain: "mobile"
tags:
  - "ble"
  - "bluetooth"
  - "ios"
  - "disconnect"
  - "reconnect"
  - "stale-data"
  - "backoff"
status: "published"
evidence_level: "E1"
created: "2026-10-31"
updated: "2026-10-31"
source: "intake-4151"
summary_plain: "电池卡从 78% 突然变成 `--`，一两秒后又恢复，看起来像数据在闪；骑行中出现会让人以为电池掉线。"
trigger: "BLE 短暂断链被当成永久断线：读数立刻清空成 --，其实 0.4 秒就重连回来了. 电池卡从 78% 突然变成 `--`，一两秒后又恢复，看起来像数据在闪；骑行中出现会让人以为电池掉线。"
verify: "走远到断链再走回来：读数不清空、不闪 `--`；真正关掉电池电源后，7 秒才显示为过期（`dataStale`）。"
provenance:
  issue: "#4151"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

电池卡从 78% 突然变成 `--`，一两秒后又恢复，看起来像数据在闪；骑行中出现会让人以为电池掉线。

## Root Cause

`didDisconnectPeripheral` → `resetSession()` 里 `reading = nil`，界面立刻清空。实际 0.4~1 秒就重连回来了。另外 `dataStale` 阈值 4.5 秒太紧：一轮失败 = 页超时 1.5 + 冷静 0.4 + 下一轮 1.05 ≈ 3 秒，连败两轮就超过 4.5 秒，正常抖动也会被判过期。

## Fix

```swift
// 1) 意外断线保留最后一次读数
resetSession(keepReading: true)

// 2) 重连退避从 0.4s 起
let ladder: [TimeInterval] = [0.4, 1, 2, 4, 8, 16, 20]

// 3) dataStale 4.5s → 7s
```
区分「意外断线」和「用户主动断开」：只有前者保留读数，后者要清空。

## Verification

走远到断链再走回来：读数不清空、不闪 `--`；真正关掉电池电源后，7 秒才显示为过期（`dataStale`）。
