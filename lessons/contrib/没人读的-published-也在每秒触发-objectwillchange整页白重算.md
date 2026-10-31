---
title: "没人读的 @Published 也在每秒触发 objectWillChange，整页白重算"
domain: "mobile"
tags:
  - "swiftui"
  - "ios"
  - "published"
  - "objectwillchange"
  - "performance"
  - "battery"
  - "combine"
status: "published"
evidence_level: "E1"
created: "2026-10-31"
updated: "2026-10-31"
source: "intake-4149"
summary_plain: "首页三栏、骑行页、连接页每秒都在重新计算视图 body（耗电、掉帧），但界面上看不到任何数字在变。"
trigger: "没人读的 @Published 也在每秒触发 objectWillChange，整页白重算. 首页三栏、骑行页、连接页每秒都在重新计算视图 body（耗电、掉帧），但界面上看不到任何数字在变。"
verify: "Instruments 的 SwiftUI View Body 计数从每秒数次降到「只有真实数据变化时」；`Publishing changes from within view updates` 警告消失。"
provenance:
  issue: "#4149"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

首页三栏、骑行页、连接页每秒都在重新计算视图 body（耗电、掉帧），但界面上看不到任何数字在变。

## Root Cause

6 个诊断字段（rxBytes / txBytes / lastTx / lastRx / probeText / discovered）没有任何界面读取，却每秒被改 3 次（轮询间隔 0.35s）。ObservableObject 的 objectWillChange 是对象级的：任何一个 @Published 变化都会让所有订阅该对象的视图重算 body。

## Fix

逐个确认读取者：没人读就删；确实要留（例如 rxBytes 用于通道探测）改成 `private(set) var`（去掉 @Published，只保留内部可写）。判据：搜索该属性名，只有写入没有读取 → 删。

## Verification

Instruments 的 SwiftUI View Body 计数从每秒数次降到「只有真实数据变化时」；`Publishing changes from within view updates` 警告消失。
