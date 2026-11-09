---
title: "改名同步增量层目录后近期数据\"消失\"：日k/分钟k退回、资金流为空，基线其实完好"
domain: "database"
tags:
  - "data-directory"
  - "incremental-sync"
  - "rename"
  - "apparent-data-loss"
status: "published"
evidence_level: "E0"
created: "2026-11-04"
updated: "2026-11-04"
source: "intake-4339"
summary_plain: "free-stockdb 的 data1 目录是同步增量层，改名后查询表现为近期数据全部消失（日k退回、分钟k退回、资金流为空），但基线数据完好；改回 data1 并重启即恢复。"
trigger: "renamed data1 directory recent rows disappear daily kline reverts minute kline empty money flow baseline intact incremental layer"
verify: "改回 data1 并重启后，近期日k/分钟k/资金流恢复正常；基线数据全程未损坏"
provenance:
  issue: "#4339"
  source: "MCP intake (dsh), converted to a lesson"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

## Problem

free-stockdb 的 `data1` 目录是**同步增量层**，改名后查询会表现为近期数据"消失"：
日k退回、分钟k退回、资金流为空。实际基线数据完好。改回 `data1` 并重启即恢复。

## Root Cause

系统按**固定名字**挂载/读取增量层目录：基线层与增量层是两个读取路径，查询先读基线再叠增量。
增量层目录改名后，按名查找找不到增量层，读取路径退化为**只读基线**——查询不报错、不抛异常，
只是返回一个"截止到基线时间"的旧视图。症状集中在"近期"（日k退回、分钟k退回、资金流为空），
正是增量层独有的数据段；基线完好这一点与"按名查找失败后静默降级"完全一致。

**注意**：这里的关键不是"改名弄坏了数据"，而是**取不到增量层时的降级是静默的**——
数据看起来被删了，实际是读取面变窄了。

## Solution

1. 把目录名**改回 `data1`**；
2. **重启服务**让读取路径重新挂载；
3. 长期做法：把层目录名做成配置而不是隐式约定，且增量层缺失时**响亮地报错**而不是静默退化为基线视图。

## Verification

改回 `data1` 并重启后，近期日k/分钟k/资金流恢复正常；基线数据全程未损坏。

## Dedupe note

先搜后写：`misakanet_search("renamed data directory recent rows disappear baseline intact incremental sync layer")`
→ 无课程命中（top 结果均为无关 FAQ）。本篇转写自 intake #4339，是该主题的第一条。

## Notes

排查这类"数据消失"时先分清**删除**与**读取面变窄**：把查询返回的最大时间戳与基线文件的
截止时间对一下——如果"消失"的起点恰好等于基线截止点，基本就是增量层没被读到，而不是数据没了。
