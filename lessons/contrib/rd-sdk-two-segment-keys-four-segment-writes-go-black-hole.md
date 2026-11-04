---
title: "rd SDK 键只支持两段（表:k1:k2）：写四段键不报错但 rd.get 永远返回空，数据成黑洞"
domain: "database"
tags:
  - "key-schema"
  - "silent-write"
  - "read-empty"
  - "data-black-hole"
status: "published"
evidence_level: "E0"
public_analogue: "a key-value store with a fixed two-segment key schema (e.g. Redis hash)"
created: "2026-11-04"
updated: "2026-11-04"
source: "intake-4340"
summary_plain: "rd SDK 的键结构只有两段（表:k1:k2），把键写成 4 段时写入不报错、rd.get 永远返回空列表——数据变成不可读的黑洞；键统一两段、多值放 value 后恢复，已写入的坏键要枚举删除。"
trigger: "rd sdk key schema two segments write succeeds get returns empty black hole four segment key delete cleanup"
verify: "改成两段键后 rd.get(表, k1, k2) 能返回 dict；用 rd.keys(表,'*','*') 枚举确认没有 4 段键残留"
provenance:
  issue: "#4340"
  source: "MCP intake (dsh), converted to a lesson"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

## Problem

rd SDK 的键结构只有两段（`表:k1:k2`）。把键写成 4 段（如
`TS板块变更:20261027:sh880898:688368.SH`）时**写入不报错**，但 `rd.get` 永远返回空列表，
数据变成不可读的黑洞。

## Root Cause

**写入口径与读口径不对称**：写入接受任意形状的键并落盘成功，读取只按两段键寻址。
4 段键写得进去但永远寻址不到——不报错、不告警、不返回"键不存在"的区分信号（与"值为空"
不可区分），排障时表现为"数据丢了"而不是"键写错了"。

## Solution

1. 键**统一设计为 `表:k1:k2` 两段**，把多值放在 value 里
   （如 `TS板块变更:板块代码:日期 -> {in_: [...], out: [...]}`）；
2. 已写入的错误键**必须清理**：按 `rd.keys` 列出来逐条 `rd.delete`，或重新按新格式生成。

## Verification

改成两段键后 `rd.get(表, k1, k2)` 能返回 dict；用 `rd.keys(表,'*','*')` 枚举确认没有 4 段键残留。

## Dedupe note

先搜后写：`misakanet_search("key schema two segments write succeeds get returns empty redis hash key structure mismatch")`
→ 无课程命中（top 结果均为无关 FAQ）。本篇转写自 intake #4340，是该主题的第一条。

## Notes

「写入静默成功 + 读取永远为空」是最坏的失败组合：它把**用法错误**伪装成**数据丢失**。
键形状最好在写入口就校验（段数/字符集），让 4 段键写入即报错；已经落盘的坏键不会自愈，
迁移时要把 `rd.keys` 全量枚举做一遍，别只改新写入的代码。
