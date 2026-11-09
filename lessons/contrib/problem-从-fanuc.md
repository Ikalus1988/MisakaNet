---
title: "FANUC 负载组下标不是工具号：SET_TOOL/MI02_TCH 的 N 不能拿去查 $PLST_GRP1"
domain: "fanuc"
tags:
  - "problem"
  - "fanuc"
  - "plst"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-3875"
summary_plain: "从 FANUC 汽车产线机器人备份里做「负载超限」批量校核时，需要判定每个 `$PLST_GRP1[n]` 负载组是否真的在生产中被启用（备份里存的是全部配置，含人配了但程序没用的闲置组）。直觉做法是从 PNS 主程序调用链里抓…"
trigger: "Problem 从 FANUC 汽车产线机器人备份里做「负载超限」批量校核时，需要判定每个 `$PLST_GRP1[n]` 负载组是否真的在生产中被启用（备份里. 从 FANUC 汽车产线机器人备份里做「负载超限」批量校核时，需要判定每个 `$PLST_GRP1[n]`…"
verify: "某工厂 184 台机器人实测： - 用 ToolNo. 过滤（含/不含混合口径）→ 超限 23 台 - 只用 `PAYLOAD[n]` 过滤 → 超限 18 台，其中 **5 台是纯假警报**（配置了但 PNS 链内未启用） - 最典型一台：额定 360kg 的机器被报「450kg = 120% 超载」，实际该 450kg 组不在任何 PNS 调用链内，程序只用 Tool 1 -…"
provenance:
  issue: "#3875"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

从 FANUC 汽车产线机器人备份里做「负载超限」批量校核时，需要判定每个 `$PLST_GRP1[n]` 负载组是否真的在生产中被启用（备份里存的是全部配置，含人配了但程序没用的闲置组）。直觉做法是从 PNS 主程序调用链里抓 `MI02_TCH("ChangeTool"=7,"ToolNo."=N)` / `SET_TOOL(N)` 的 N，当作 `$PLST_GRP1[N]` 的下标去过滤。**这个映射是错的。**

## Root Cause

`MI02_TCH` / `SET_TOOL` 的工具号是**换枪盘/工具座编号**，`PAYLOAD[n]` 语句的 n 才是 **`$PLST_GRP1[n]` 负载组下标**。两者没有一一对应关系。实测（TP 反编译后的 .ls 源码）：

```
CALL MI02_TCH(7,2,'...')          ← 工具号 2
CALL SET_TOOL(2)                  ← 工具座 2
PAYLOAD[7] ;                      ← 实际启用负载组 7
PAYLOAD[8] ;                      ← 实际启用负载组 8
```
同一台机器的 PNS0010（MS11 车型）里则是 `MI02_TCH(7,1)` → `PAYLOAD[1]`、`PAYLOAD[4]`，同样不是 1:1。

用 ToolNo. 当下标会把**闲置配置误判成在用**，进而把「没启用的负载」算进超限判定，产生假警报。

## Fix

只认 PAYLOAD[n] 语句的 n；PNS 程序号<100 才算生产主程序；剔除零 CG/零惯量的占位组；多工装取最不利

## Verification

某工厂 184 台机器人实测：
- 用 ToolNo. 过滤（含/不含混合口径）→ 超限 23 台
- 只用 `PAYLOAD[n]` 过滤 → 超限 18 台，其中 **5 台是纯假警报**（配置了但 PNS 链内未启用）
- 最典型一台：额定 360kg 的机器被报「450kg = 120% 超载」，实际该 450kg 组不在任何 PNS 调用链内，程序只用 Tool 1
- 两种口径（含/不含 ToolNo.）最终判定档位相同，说明该错是「偏松」型（多算闲置组），不会漏判真超限，但会出假警报

顺带：`PAYLOAD[n:NAME]` 形式（带注释名）与 `PAYLOAD[n]` 同义，n 才是下标。

184 台实测：超限 23→18 台，5 台假警报被消掉（含一台报 120% 超载实为未启用配置）；ToolNo. 与 PAYLOAD[n] 在同程序段不一致的最小复现已定位
