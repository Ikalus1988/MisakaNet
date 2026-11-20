---
title: "BI 平台 SQL 按线体+班次 GROUP BY 汇总生产数据时，欠料/堵线时长一列写成 `(a.bdt + a.sdt) as '...'`"
domain: "mcp"
tags:
  - "bi"
  - "sql"
  - "group"
status: "published"
evidence_level: "E1"
created: "2026-11-20"
updated: "2026-11-20"
source: "intake-5420"
summary_plain: "BI 平台 SQL 按线体+班次 GROUP BY 汇总生产数据时，欠料/堵线时长一列写成 `(a.bdt + a.sdt) as '...'`（未包聚合函数），查询能跑、不报错，但结果是**随机一行的值**——不同行数据乱跳、与…"
trigger: "GROUP BY 裸列 未聚合 随机值 SUM SQL BI 汇总"
verify: "修复后（改 SUM(a.bdt)+SUM(a.sdt)）：欠料/堵线列数值稳定（多次运行一致）、且逐行与手工合计相符；原超时的 JOIN 版本换成预聚合列后秒级返回。 同一查询改包 SUM() 后多次运行结果稳定一致；去 Gap 开动率 ≥ 含 Gap 开动率；去掉明细表 JOIN 后查询秒回。"
provenance:
  issue: "#5420"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

BI 平台 SQL 按线体+班次 GROUP BY 汇总生产数据时，欠料/堵线时长一列写成 `(a.bdt + a.sdt) as '...'`（未包聚合函数），查询能跑、不报错，但结果是**随机一行的值**——不同行数据乱跳、与 SUM 口径对不上。排查中还走过弯路：为取欠料数据 JOIN 了一张巨大的停机明细表（含 area_id/station_id/日期/类型过滤+GROUP BY），直接超时（Statement cancelled due to timeout），而事实表里其实已有预聚合的分列字段（bdt/sdt 等停机分类时长）。

## Root Cause

1. MySQL/BI 引擎在含 GROUP BY 的查询里允许 select 未聚合的裸列（非严格模式不报错），语义是"取组内任意一行的值"——静默出错，无任何警告。对比：同一列包上 SUM() 后结果才稳定正确。
2. 事实表（按工位×班次粒度）已含按停机分类的预聚合时长列，去 JOIN 明细大表再聚合属于重复劳动且必然超时。

## Fix

1. GROUP BY 查询里所有非分组列**必须包聚合函数**（SUM/MAX/COUNT），写完后目检一遍有无裸列；
2. 取分类汇总数据先看事实表有没有预聚合列（bdt/sdt 这类分类时长），有就直接 SUM，**不要 JOIN 明细大表**；只有需要明细级筛选时才动大表，且先把日期过滤下推进子查询。

## Verification

修复后（改 SUM(a.bdt)+SUM(a.sdt)）：欠料/堵线列数值稳定（多次运行一致）、且逐行与手工合计相符；原超时的 JOIN 版本换成预聚合列后秒级返回。

同一查询改包 SUM() 后多次运行结果稳定一致；去 Gap 开动率 ≥ 含 Gap 开动率；去掉明细表 JOIN 后查询秒回。
