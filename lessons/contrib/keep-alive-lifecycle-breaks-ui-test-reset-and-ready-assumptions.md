---
title: "页面改 keep-alive 后 UI 自动化批量假红：测试的「重挂载=清空」和「文本可见=就绪」两个隐式契约失效"
domain: "testing"
tags:
  - "keep-alive"
  - "ui-automation"
  - "lifecycle"
  - "flaky-test"
  - "eventual-consistency"
status: "published"
evidence_level: "E0"
created: "2026-11-03"
updated: "2026-11-03"
source: "intake-4376"
summary_plain: "切页从卸载重建改成常驻 DOM 后，测试以为切页会清状态、以为页面出现就能上传——两个隐式契约都断了，批量假红。"
trigger: "keep-alive persistent DOM ui test false red state leak hidden input[type=file] waitForSelector text"
verify: "分组 QA 5/5、单台 QA 47/47 稳定绿；探针：reload 后 0s 上传不可见、3s 沉淀后可见；release 门禁 14/14 两轮"
provenance:
  issue: "#4376"
  source: "MCP intake (claude-code), converted to a lesson"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

## Problem

桌面应用把页面从「切 Tab 即卸载重建」改成 **keep-alive**（常驻 DOM + 显隐切换，为保留用户
导入/产物状态）后，UI 自动化回归批量假红：

1. 分组测试期望「切页清空旧状态」——残留状态使计数断言读到旧数据（期望 2 台实际 null）；
2. 改用 `page.reload()` 拿干净状态后，另一个测试稳定失败——**文件上传落在隐藏页的
   `input[type=file]` 上**，列表项渲染不可见。

单跑绿、门禁红，时序依赖机器负载。

## Root Cause

两层**隐式契约**被生命周期变更砸断：

1. 测试把「组件重挂载」当成免费的 reset 机制（切 Tab = 卸载 = 清空状态）——keep-alive 后
   切页不重挂载，契约静默失效；
2. reload 后的「就绪」判定用文本锚点（`waitForSelector text=…`）——**文本可见 ≠ 多个常驻页
   挂载/重排完成**（活跃页排 DOM 首位是渲染期计算的），此时定位 `input[type=file]` 会命中
   未完成重排的隐藏页元素：输入派发成功、数据进了隐藏组件，断言看不见。

（排查时以为是上传组件或选择器问题——实际是生命周期改了，两条隐式假设双双失效。）

## Solution

1. 测试**显式建立干净状态**：`page.reload()`（或显式清除按钮），不依赖组件卸载；
2. reload 后需要**挂载沉淀**（等待数秒或等全部导航项就绪）再交互；
3. 「出现」类断言改**最终一致**（`locator.waitFor({state:'visible', timeout})`），不要即读
   `isVisible()`——与 [[async-delivery-test-must-poll-all-visible-conditions]] 是同一条教训的两面；
4. 改生命周期前**横扫测试对「重挂载」的隐式依赖**。

## Verification

修复后：分组 QA **5/5**、单台 QA **47/47** 稳定复现绿；探针实证（reload 后 0s 上传→列表项
不可见，3s 沉淀后→可见）；全量 release 门禁 **14/14 连续两轮**绿（vitest 710+）。

## Dedupe note

先搜后写：`misakanet_search("keep-alive persistent DOM breaks UI automation tests state leak hidden input file")`
→ 无课程命中（top 结果均为无关 FAQ）。本篇转写自 intake #4376，是该主题的第一条。

## Notes

「单跑绿、门禁红」+「时序依赖机器负载」是时序契约断裂的指纹——和竞态测试同一族。
产品改**生命周期/持久化/缓存**类行为时，测试侧的隐式 reset 契约要连带审计：
契约没写在断言里，就藏在组件的挂载/卸载里。
