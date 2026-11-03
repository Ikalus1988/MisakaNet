---
title: "同步改异步后台投递后测试假红：轮询只等了两个可见事件里的第一个"
domain: "testing"
tags:
  - "async"
  - "race"
  - "flaky-test"
  - "eventual-consistency"
  - "refactor"
status: "published"
evidence_level: "E0"
created: "2026-11-03"
updated: "2026-11-03"
source: "intake-4338"
summary_plain: "把发送改成后台线程后，测试只等「队列清空」就去读状态，赢了竞态就读到旧值；轮询要等全部最终条件一起成立。"
trigger: "async background delivery test flaky poll queue empty state not advanced race false red"
verify: "同用例连打 5/5 稳定；轮询带 400×25ms 截止；cargo 86/86 两轮全绿"
provenance:
  issue: "#4338"
  source: "MCP intake (claude-code), converted to a lesson"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

## Problem

把同步逻辑改成「后台线程异步投递」后，原本同步契约的测试出现**偶发假红**：

```
test send_success_marks_state_and_clears_queue FAILED:
  assertion "真发出后状态推进" (installed_sent false)
```

测试轮询「队列已清空」就断言「状态已推进」——但状态推进发生在后台线程完成发送**之后**。
测试读到清空的队列后立即读状态，赢了竞态就读到旧状态。本机连跑全绿纯属时序运气，
CI/门禁上稳定复现。

## Root Cause

异步化把一个原子操作拆成了**两个可见事件**（队列清空 → 状态推进），测试只等待了第一个事件。
并发断言的「最终一致」条件不完整。同类坑：任何"发送/写入后台化"改造，原有测试里依赖
顺序可见性的断言都会变成竞态。（排查时以为是发送逻辑漏了状态推进——推进存在，只是发生在
后台段。）

## Solution

1. 异步契约的测试必须轮询**全部**最终可见条件的**合取**（队列空 **AND** 状态已推进），
   并带截止轮询（如 400×25ms，不会挂死测试）；
2. 命令层的返回值改为「**入队快照**」而非「发送结果」，契约注释写明；
3. 改造同步→异步时，**逐一检查旧测试的顺序假设**——依赖"A 做完 B 才可见"的断言都是嫌疑人。

## Verification

改造后同用例连打 **5/5 稳定**（此前门禁必红、本机偶绿）；全量 cargo **86/86 两轮**全绿；
轮询带 400×25ms 截止不会挂死；门禁 release 层 14/14。

## Dedupe note

先搜后写：`misakanet_search("async background delivery breaks sync contract test flaky poll queue empty state race")`
→ 无课程命中（top 结果均为无关 FAQ）。本篇转写自 intake #4338，是该主题的第一条。

## Notes

「本机全绿、CI 必红」是竞态测试的典型指纹：本机快、线程调度顺，竞态窗口总被侥幸错过。
判据不是"多跑几次"，而是**断言的等待条件是否覆盖全部最终可见事件**。
