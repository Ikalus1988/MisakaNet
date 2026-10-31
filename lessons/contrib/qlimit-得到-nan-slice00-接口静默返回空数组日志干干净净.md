---
title: "+q.limit 得到 NaN → slice(0,0) → 接口静默返回空数组，日志干干净净"
domain: "nodejs"
tags:
  - "nodejs"
  - "express"
  - "nan"
  - "slice"
  - "silent-failure"
  - "query-params"
  - "api"
status: "published"
evidence_level: "E1"
created: "2026-10-31"
updated: "2026-10-31"
source: "intake-4152"
summary_plain: "客户端带一个非法参数（`?limit=abc`），接口不报错、不抛异常、日志干净，就是「没数据」。用户以为是数据丢了，实际是解析成了空数组。"
trigger: "+q.limit 得到 NaN → slice(0,0) → 接口静默返回空数组，日志干干净净. 客户端带一个非法参数（`?limit=abc`），接口不报错、不抛异常、日志干净，就是「没数据」。用户以为是数据丢了，实际是解析成了空数组。"
verify: "`curl '...?limit=abc'` 返回默认条数而不是 `[]`；`?limit=-5`、`?limit=1e9`、`?limit=` 都落在 [lo,hi] 区间内。"
provenance:
  issue: "#4152"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

客户端带一个非法参数（`?limit=abc`），接口不报错、不抛异常、日志干净，就是「没数据」。用户以为是数据丢了，实际是解析成了空数组。

## Root Cause

```js
Math.min(200, +q.limit)   // +'abc' = NaN → Math.min(NaN,200) = NaN
all.slice(0, NaN)         // = slice(0,0) = []
```
整条链路没有一处会抛错：NaN 参与 Math.min 仍是 NaN，slice 收到 NaN 当 0 处理，响应就是 `[]`。

## Fix

统一走参数解析函数，任何数值参数都不允许直接 `+`：

```js
function intParam(v, def, lo, hi) {
  const n = Number.parseInt(v, 10);
  if (!Number.isFinite(n)) return def;
  return Math.min(hi, Math.max(lo, n));
}
```
涉及 `/api/rides`、`/ddt/points/nearby`（radius + limit）、`/ddt/points`（limit + offset）。再加一条：列表接口响应里带 `total`，空数组时能区分「真没有」和「参数解析坏了」。

## Verification

`curl '...?limit=abc'` 返回默认条数而不是 `[]`；`?limit=-5`、`?limit=1e9`、`?limit=` 都落在 [lo,hi] 区间内。
