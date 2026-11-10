---
title: "飞书 doc_append 往 callout 里写嵌套列表：success 但 degrade_code=1010"
domain: "feishu"
tags:
  - "problem"
  - "api"
  - "doc"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-3945"
summary_plain: "飞书 doc_append 往 callout 里写嵌套列表：success 但 degrade_code=1010"
trigger: "飞书 doc_append 往 callout 里写嵌套列表：success 但 degrade_code=1010"
verify: "某分析报告（约 42k 字符）向首页 callout 写入含 5 条 bullet 的管理层摘要： - 第一次：`success:true` + `warnings:[degrade_code=1010]`，回读发现 callout **内容全空** - 改为扁平段落（去掉 bullet，多条用软换行）后重写：warnings 消失，回读内容完整 - 再用…"
provenance:
  issue: "#3945"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

用飞书文档 API（`doc_update` / `doc_append`，markdown 形式）向 `<callout>` 高亮块里写内容，
内容含**嵌套列表**（callout 内的 `- xxx` bullet）时，返回 `success: true`，
但响应带警告 `degrade_code=1010, msg=Nesting still failed after degrade. Simplify the nesting structure and retry`。
**实际结果是 callout 被清空** —— 原有内容丢失，新内容也没进去，只剩一个空壳 `<callout emoji="⭐"></callout>`。
不检查响应里的 `warnings` 字段就会静默丢内容。

## Root Cause

飞书 callout 块的嵌套层级有限制。markdown 里 callout 内部再嵌 bullet list，
转换器先降级（degrade）为段落拼接；若降级后仍超限（`Nesting still failed after degrade`），
**整个块内容写入失败**，而 HTTP 响应仍是 `success: true` ——
只在 `warnings` 数组里给出 degrade_code=1010。调用方若只看 `success`，会以为写成功了。

## Fix

callout 内用扁平段落不用列表；每次写后检查响应 warnings 字段；写后 doc_fetch 回读校验

## Verification

某分析报告（约 42k 字符）向首页 callout 写入含 5 条 bullet 的管理层摘要：
- 第一次：`success:true` + `warnings:[degrade_code=1010]`，回读发现 callout **内容全空**
- 改为扁平段落（去掉 bullet，多条用软换行）后重写：warnings 消失，回读内容完整
- 再用 `doc_delete_blocks_by_ids` 清掉空壳，文档结构完好（outline 校验通过）

扁平结构重写后 warnings 消失、回读内容完整；空壳用 doc_delete_blocks_by_ids 清除，outline 校验通过
