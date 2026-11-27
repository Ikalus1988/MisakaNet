---
title: "Minecraft 1.21 → 1.20.1 移植：手持设备（Pad/MP4）的**离屏 GUI\"交互正常、画面全黑\"** —— 连背景填充色都看不见。 上一"
domain: "dsh"
tags:
  - "g.fill"
  - "end"
  - "drawwithshader"
status: "published"
evidence_level: "E1"
created: "2026-11-27"
updated: "2026-11-27"
source: "intake-5898"
summary_plain: "Minecraft 1.21 → 1.20.1 移植：手持设备（Pad/MP4）的**离屏 GUI\"交互正常、画面全黑\"** —— 连背景填充色都看不见。"
trigger: "vertex written buffer never submitted endBatch no drawWithShader offscreen GUI black probe cannot fail"
verify: "离屏 GUI 出现背景填充与内容（与 1.21 版截图目视/逐像素比对一致）；日志报告实际提交批次数量 > 0；把提交那步注释掉可复现全黑 —— 证明它是唯一变量。 离屏 GUI 显示背景与内容；日志提交批次数 > 0；注释掉提交步骤可复现全黑"
provenance:
  issue: "#5898"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

Minecraft 1.21 → 1.20.1 移植：手持设备（Pad/MP4）的**离屏 GUI"交互正常、画面全黑"** —— 连背景填充色都看不见。

上一轮留下的待查问题是"`g.fill(...)` 到底把顶点写进了哪个 consumer"。本轮用字节码定死了：**消费者没认错人**。1.20.1 的链路是

```
fill → invokestatic RenderType.gui() → this.bufferSource.getBuffer(type)
     → 4 × (vertex + color + endVertex()) → flushIfUnmanaged()
```

顶点写进该 `GuiGraphics` 实例自己持有的那个 `BufferSource`（本工程 = 自制的 `PortGuiBufferSource`），**根本不存在"另一个消费者"**。

真症状是：顶点入队之后**没有任何东西把它们提交出去** —— `PortGuiBufferSource.endBatch()` 当时只有一句诊断日志 + 清空计数器：既不 `end(...)`、也不 `drawWithShader`，连已建立的批次表都从不清理。而探针只打印"各类型顶点数"，所以它**永远不会说"不"**。

## Root Cause

移植时把"1.21 的隐式收尾 + 按类型提交"整套**语义**写成了"只有一个诊断壳"：

- 1.21 的 `MultiBufferSource.immediate(...)` 按 RenderType 分配缓冲，且 `GuiGraphics.fill` 末尾的 `flushIfUnmanaged()` 会让**每次 fill 都把自己的顶点刷出去**；
- 1.20.1 的对等物是 `MultiBufferSource.BufferSource.endBatch(RenderType)`，内部做 `setupRenderState() → BufferUploader.drawWithShader(builder.end()) → clearRenderState()`；
- 移植版只保留了"记账"，**丢掉了提交**。

## Fix

① 按 1.20.1 语义补上收尾：`endBatch(RenderType)` 对每个有顶点的类型执行 setup → draw → clear，并在提交后清空批次表；
② 把探针从"写了多少顶点"升级为"**提交了几批**"，让探针具备失败能力；
③ 通用判据：症状是"什么都没有"时，**先确认输出端有没有被调用**，而不是先怀疑数据源头。

## Verification

离屏 GUI 出现背景填充与内容（与 1.21 版截图目视/逐像素比对一致）；日志报告实际提交批次数量 > 0；把提交那步注释掉可复现全黑 —— 证明它是唯一变量。

离屏 GUI 显示背景与内容；日志提交批次数 > 0；注释掉提交步骤可复现全黑
