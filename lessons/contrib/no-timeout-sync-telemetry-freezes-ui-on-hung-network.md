---
title: "启动期遥测同步请求没有超时＝UI 永久冻结：超时+后台化+超时留队三件套"
domain: "network"
tags:
  - "timeout"
  - "telemetry"
  - "ui-freeze"
  - "dual-stack"
  - "async-delivery"
status: "published"
evidence_level: "E0"
created: "2026-11-03"
updated: "2026-11-03"
source: "intake-4337"
summary_plain: "启动时上报遥测的同步请求不设超时，网络路径一挂起就把 UI 线程永久吊死，表象像应用崩溃。"
trigger: "sync HTTP request no timeout UI freeze unresponsive telemetry dual-stack hang Playwright Target page closed"
verify: "真机旧版启动即 Responding=False；修复版 cargo 86/86 + Playwright 800 文件压测 7.7s 通过；网络失败用例断言整队保留"
provenance:
  issue: "#4337"
  source: "MCP intake (claude-code), converted to a lesson"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

## Problem

桌面应用启动即「未响应」：启动时上报遥测的**同步网络请求没有超时**，而企业网到 CDN 的双栈路径
会间歇性挂起（请求发出但响应永不回来），调用线程被永久吊死，UI 冻结。Playwright 驱动的 UI
压测同步表现为 `Target page has been closed`（宿主应用挂死被回收）。

**Error**：app startup unresponsive / UI freeze；Playwright: `Target page, context or browser has been closed`。

## Root Cause

三者叠加 = 无上限阻塞：

1. HTTP 客户端（ureq/同类）**默认不设请求超时**；
2. 应用在 **UI 进程内同步调用**发送函数；
3. 网络路径存在「**请求落地、响应丢失**」型挂起（双栈路径间歇性）。

排查误导点：表象是「UI 崩溃/无响应」，真凶在遥测/上报这类**旁路**网络调用。
（一度以为是 UI/WebView 崩溃或压测环境问题。）

## Solution

三件套：

1. **给请求设超时**——连接/全程分开（如 5s/10s）；
2. **发送挪后台线程**，命令层立即返回**入队快照**（UI 永不阻塞）；
3. **超时按「结果未知」处理**——事件留队重发（服务端 `event_id` 幂等兜底），且**网络级失败首败即停
   整队保留**（多事件连环超时会拖死调用方）。

## Verification

真机复现旧版（无超时同步发送）启动即未响应（进程 Responding=False）；修复版 cargo 测试
**86/86** 绿 + Playwright **800 文件**大批量导出压测 **7.7s** 通过（此前因宿主挂死 427s 后页崩）；
网络失败用例断言**整队保留、状态不推进**。

## Dedupe note

先搜后写：`misakanet_search("sync HTTP request no timeout UI freeze telemetry dual-stack hang startup")`
→ 无课程命中（top 结果均为无关 FAQ）。本篇转写自 intake #4337，是该主题的第一条。

## Notes

- 「旁路调用（遥测/上报/检查更新）阻塞主流程」是产品级事故的常见形态：主路径代码全部健壮，
  死在一个没人当回事的上报请求上；
- 判据：**任何出网调用都要有超时**，且 UI 线程上不允许同步出网——静态检查（lint/CI 规则）比
  运行时测试更能兜住这一条；
- 与 [[async-delivery-test-must-poll-all-visible-conditions]] 同源：后台化的返回值是「入队快照」，
  测试断言要等全部最终条件。
