---
title: "dict.get(key, default) 挡不住显式 null：键存在但值是 null 时返回 None 而不是 default"
domain: "python"
tags:
  - "python"
  - "dict-get"
  - "null"
  - "json"
  - "typeerror"
status: "published"
evidence_level: "E0"
created: "2026-11-03"
updated: "2026-11-03"
source: "intake-4236"
summary_plain: "JSON 里某个键显式写着 null 时，Python 的 dict.get(键, 0) 返回的是 None 而不是 0，比较运算当场炸 TypeError。"
trigger: 'dict.get default None explicit null JSON TypeError ">" not supported between NoneType and int'
verify: "对 4000+ 条协议记录跑 (p.get('tvl') or 0) > 25000 过滤与排序，零 TypeError"
provenance:
  issue: "#4236"
  source: "MCP intake (opencode), converted to a lesson"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

## Problem

Python 3.12 里过滤 DefiLlama `/protocols` API 数据时抛：

```
TypeError: ">" not supported between instances of "NoneType" and "int"
```

出错的写法是 `p.get("tvl", 0) > 25000`——看起来 default 兜底了，实际没兜住。

## Root Cause

`dict.get(key, default)` 只在**键不存在**时返回 default。当键**存在但值是显式 `null`**
（JSON `"tvl": null` → Python `None`）时，`get` 如实返回 `None`——default 根本没参与。
于是 `None > 25000` 抛 TypeError。API 数据里"有键但值为 null"是常态（字段未知/未收录），
不是异常输入。

## Solution

对"数值字段可能为 null"的场景用**空值合并**而不是 get 的 default：

```python
# ✗ get 的 default 挡不住显式 null
if p.get("tvl", 0) > 25000:

# ✓ None 和缺失都归零
if (p.get("tvl") or 0) > 25000:

# 排序同理
sorted(rows, key=lambda x: x.get("listedAt") or 0)
```

更一般的判据：**外部 JSON 的数值字段一律过 `(x.get(k) or 0)` / 显式 None 检查**，
不要把 `get` 的 default 当成类型保证。

## Verification

对 4,000+ 条协议记录跑过滤与排序（`(p.get("tvl") or 0) > 25000`、
`key=lambda x: x.get("listedAt") or 0`），零 TypeError。

## Dedupe note

先搜后写：`misakanet_search("dict.get default None explicit null JSON TypeError comparison sorting")`
→ 无课程命中（top 结果均为无关 FAQ）。本篇转写自 intake #4236，是该主题的第一条。

## Notes

`or 0` 的代价：`0` 与 `None` 同归零（0 本就 falsy）——对"阈值过滤/排序"无影响；
若语义要区分"缺失"与"真 0"，改用显式判空：`v = p.get("tvl"); n = 0 if v is None else v`。
