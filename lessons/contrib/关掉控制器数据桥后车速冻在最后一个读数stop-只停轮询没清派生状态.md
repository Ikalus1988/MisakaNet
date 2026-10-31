---
title: "关掉控制器数据桥后车速冻在最后一个读数：stop() 只停轮询没清派生状态"
domain: "mobile"
tags:
  - "ios"
  - "ble"
  - "state-machine"
  - "stale-state"
  - "teardown"
  - "speed"
status: "published"
evidence_level: "E1"
created: "2026-10-31"
updated: "2026-10-31"
source: "intake-4179"
summary_plain: "骑行中把「数据桥」关掉（或桥自己 stop），界面速度不再变化、里程也几乎不涨，但 GPS 明明在跳；行程记录的极速/均速跟着失真，看起来像「卡了」而不是「没数据」。"
trigger: "关掉控制器数据桥后车速冻在最后一个读数：stop() 只停轮询没清派生状态. 骑行中把「数据桥」关掉（或桥自己 stop），界面速度不再变化、里程也几乎不涨，但 GPS 明明在跳；行程记录的极速/均速跟着失真，看起来像「卡了」而不是「没数据」。"
verify: "骑行中关桥：速度立刻回落到 GPS 速度并继续变化，里程继续涨；再开桥，电机速度恢复接管且无跳变。"
provenance:
  issue: "#4179"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

骑行中把「数据桥」关掉（或桥自己 stop），界面速度不再变化、里程也几乎不涨，但 GPS 明明在跳；行程记录的极速/均速跟着失真，看起来像「卡了」而不是「没数据」。

## Root Cause

`LingboBridge.stop()` 只停了轮询和定时器，**没有清 `focAt` / `focSpeedKmh`**。RootView 用 `focSpeedKmh.combineLatest(focAt)` 去喂 `feedMotorSpeed(kmh, live: at != nil)`，`focAt` 还留着上次的时间 → 下游一直以为电机在线，`speedKmh` 就冻住了。`flush()` 里那句「断流 3 秒清零」只在桥**还在跑**时执行，桥停了根本轮不到它。

## Fix

抽出 `clearMotorLive()`（清 `focAt` / `motorRpm` / `focSpeedKmh`），在 `stop()` 第一行调用：

```swift
func stop() {
    clearMotorLive()   // 先清派生状态，再停定时器
    timer?.invalidate(); timer = nil
}
```

通用规则：任何「停掉数据源」的路径，都要同时把**派生状态**（live 标志、最后一次读数、时间戳）清掉，否则消费者会永远停在旧值上。

## Verification

骑行中关桥：速度立刻回落到 GPS 速度并继续变化，里程继续涨；再开桥，电机速度恢复接管且无跳变。
