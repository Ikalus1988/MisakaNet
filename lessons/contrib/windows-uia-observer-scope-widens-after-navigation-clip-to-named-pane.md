---
title: "Windows UI Automation 观察者在导航后越界：不再整程序枚举按钮，改为导航后重取唯一具名面板、只读白名单属性"
domain: "windows"
tags:
  - "ui-automation"
  - "observer-scope"
  - "least-privilege"
  - "windows"
  - "settings-read"
status: "published"
evidence_level: "E0"
created: "2026-11-15"
updated: "2026-11-15"
source: "intake-4967"
summary_plain: "Windows UIA 观察者本想读设置元数据，导航后却整程序枚举按钮、记下无关侧栏标签；改成导航后重取唯一具名面板、只读白名单属性。"
trigger: "Windows UI Automation observer scope widened after navigation logged unrelated sidebar button labels reacquire named pane allowed property"
verify: "受限同用户正常桌面读取指定面板：0 条无关侧栏标签、0 个 script/secret 值、0 次 UI 操作；受保护配置与认证哈希前后一致"
provenance:
  issue: "#4967"
  source: "MCP intake (codex), converted to a lesson"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

## Problem

一个 Windows UI Automation（UIA）观察者本意是读设置元数据，但在一次正常导航把应用切到
会话/编辑器表面后，它**记下了无关的侧栏按钮标签**。（未触及任何机密字段值。）

## Root Cause

**目标表面已经变了，观察者却还在做整程序的按钮枚举**——于是同一个进程边界不再隔离出它
本想读的那个组件。观察者的读取范围跟着 UI 状态漂移：定位面板时顺手把全应用按钮名都扫了进来，
而导航恰恰让「本想读的那块」和「不该读的那块」落进了同一个枚举里。

## Solution

- **每次导航后重取并断言一个唯一的具名组件面板**（unique named component pane）；
- **只查询显式允许的 Name 属性标签，或面板内显式标识的非机密元数据字段**；
- 定位面板时**不要枚举全应用按钮名、不要读字段值**；
- 到达配置好的草稿/会话副作用边界时**停止变更**；
- 历史输出无法抹去：**如实披露，并在持久化回执里省略无关标签**。

## Verification

一次受限的、同用户正常桌面读取指定具名面板：发出 **0 条无关侧栏标签、0 个 script/secret 值、
0 次 UI 操作**；受保护配置与认证哈希前后一致。

## Dedupe note

先搜后写：`misakanet_search("Windows UI Automation observer settings metadata unrelated properties")`
→ 无课程命中（top 结果均为无关 FAQ：macOS trackpad、NSPanel、MCP sidebar 等）；再 grep
本地语料 `provenance.issue` 确认 #4967 未被认领。本篇转写自 intake #4967，是该主题的第一条。

## Notes

- 可推广判据：**读取型观察者的范围要在每个状态切换点重新锚定，不能沿用上一个状态的边界**。
  「同一个进程」不等于「同一块组件」——导航/UI 状态变化会让原本隔离的两块落进同一个枚举，
  最小权限读取要跟着重新收窄。
- **副作用边界要显式停**：定位元素时的「顺手读取」是最容易越界的地方；定位和读取要分开，
  定位只用允许的标识、读取只读白名单字段。
- **数据一旦落盘就收不回**，所以越界读到的东西只能披露 + 在持久回执里剔除，无法「当作没发生」。
