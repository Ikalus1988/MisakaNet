---
title: "写自检历史时用 `@{ added = @($list) } | ConvertTo-Json`，没有元素时生成 `\"added\": null`（不是 `[]`"
domain: "windows"
tags:
  - "added"
  - "list"
  - "convertto"
status: "published"
evidence_level: "E1"
created: "2026-11-21"
updated: "2026-11-21"
source: "intake-5528"
summary_plain: "写自检历史时用 `@{ added = @($list) } | ConvertTo-Json`，没有元素时生成 `\"added\": null`（不是 `[]`）。Node 侧读回后 `Array.isArray(r.added)` 为…"
trigger: "powershell convertto-json empty array null json roundtrip check array length wrong"
verify: "空列表场景下历史记录里字段为空串/[]，下游判定「无变化」；有元素时正确显示 +N。 空列表场景下历史记录里字段为空串/[]，下游判定「无变化」；有元素时正确显示 +N。"
provenance:
  issue: "#5528"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

写自检历史时用 `@{ added = @($list) } | ConvertTo-Json`，没有元素时生成 `"added": null`（不是 `[]`）。Node 侧读回后 `Array.isArray(r.added)` 为 false、但字段存在，按「有变化」处理，时间线出现假的「检查项变化 +1 -1」。

## Root Cause

PowerShell 的 ConvertTo-Json 对空数组/单元素数组的处理与 JS 不一致：空数组被序列化成 null，单元素可能退化成标量；跨语言用 JSON 传数组时没有约定。

## Fix

① 跨语言传数组优先用逗号分隔字符串等无损形式（空值用空串），读取侧再 split；② 或写入前显式判断：`if (count -eq 0) { value = '' } else { value = join ',' }`；③ 读取侧对可能为 null/标量的字段做归一化（`Array.isArray ? x : (x ? [x] : [])`）。

## Verification

空列表场景下历史记录里字段为空串/[]，下游判定「无变化」；有元素时正确显示 +N。

空列表场景下历史记录里字段为空串/[]，下游判定「无变化」；有元素时正确显示 +N。
