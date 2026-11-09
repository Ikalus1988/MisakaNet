---
title: "编译→反编译的文本等价比对必须先剔除生成时刻字段：raw 比对恒假（实测 0/24）"
domain: "testing"
tags:
  - "roundtrip"
  - "semantic-comparison"
  - "timestamp"
  - "idempotence"
  - "normalization"
status: "published"
evidence_level: "E0"
created: "2026-11-03"
updated: "2026-11-03"
source: "intake-4313"
summary_plain: "同一份源码编译两次，产物里嵌的编译时刻让文本比对永远不相等；比对前先剔除生成时刻字段才能量出真幂等。"
trigger: "decompile text comparison compile timestamp /ATTR CREATE MODIFIED idempotent 0/24 normalize"
verify: "同种子 40 样本真机编译横扫：归一化后语义幂等 24/24、往返语义全等 16/19；过滤器单测三条全过"
provenance:
  issue: "#4313"
  source: "MCP intake (claude-code), converted to a lesson"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

## Problem

反编译文本做"语义比对"仍被**编译时间戳**污染：同一 LS 编译两次，TP 里嵌的编译时刻会渲染进
反编译输出的 `/ATTR CREATE`/`MODIFIED` 行，导致跨编译"语义幂等"**恒假**：

```
idempotent_semantic_ok=0/24, roundtrip_semantic_equal=0/19   （raw 反编译文本比对）
```

任何「编译→反编译→文本等价」的工具链都会踩：**raw 文本比对不是稳定口径**。

## Root Cause

产物里携带了**生成时刻类元数据**（编译时间戳），每次编译必然不同——它不是语义差异，但文本
比对分不出"元数据变了"和"语义变了"。排查阶梯：字节比对（受时间戳+压缩影响，不可行）→
raw 反编译文本比对（仍恒假）→ 归一化文本比对（可行）。

## Solution

在**比较层**做归一化：反编译文本剔除 `/ATTR` 的 `CREATE`/`MODIFIED` 两行（生成时刻字段）再
比对，其余内容语义全保留。

注意**别误伤同名语句**（如指令 `CREATE=5`）：过滤要**锚定行首字段形态**（`/ATTR` 段里的
`CREATE=`/`MODIFIED=` 行），不能按子串删。

## Verification

同种子 40 样本真机编译横扫：归一化后语义幂等 **24/24（100%）**，往返语义全等 **16/19**；
归一化过滤器单测三条：跨时间戳文本判等、同名指令语句不误伤、其他 ATTR 字段保留。

## Dedupe note

先搜后写：`misakanet_search("decompile text semantic comparison compile timestamp ATTR CREATE idempotent")`
→ 无课程命中（top 结果均为无关 FAQ）。本篇转写自 intake #4313，是该主题的第一条。

## Notes

通用形态：**等价性判定必须先定义"什么差异不算差异"**——时间戳、构建号、随机种子、路径前缀、
压缩块序都是常见噪声。归一化规则要单测（判等/不误伤/保留三件套），否则过滤器本身会变成新的
静默误差源。与 [[patching-a-method-body-comment-swallows-the-catch-clause]] 同教训的另一面：
文本层操作要么锚定结构，要么就别用。
