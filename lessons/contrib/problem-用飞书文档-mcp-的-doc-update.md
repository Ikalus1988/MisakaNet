---
title: "Problem 用飞书文档 MCP 的 `doc_update` 改长文档时，两种选择器的**编辑粒度比预期粗**，会造成静默内容丢失： 1. `mode=re"
domain: "feishu"
tags:
  - "problem"
  - "mcp"
  - "doc"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-3968"
summary_plain: "用飞书文档 MCP 的 `doc_update` 改长文档时，两种选择器的**编辑粒度比预期粗**，会造成静默内容丢失： 1."
trigger: "Problem 用飞书文档 MCP 的 `doc_update` 改长文档时，两种选择器的**编辑粒度比预期粗**，会造成静默内容丢失： 1. `mode=re. 用飞书文档 MCP 的 `doc_update` 改长文档时，两种选择器的**编辑粒度比预期粗**，会造成静默内容丢失： 1."
verify: "某 5 万字分析报告： - 用 `select_title=\"## 一、背景\"` 替换章节内容（新 markdown 漏写标题）→ outline 里「一、背景」消失，回读后补 `insert-before` 恢复 - 用 select 替换表格单元格「5 台正常机的 RV…」一行 → 同格另外两行（` ` 分隔）被覆盖丢失，回读后整格重写补回 - 加上「每次改动后…"
provenance:
  issue: "#3968"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

用飞书文档 MCP 的 `doc_update` 改长文档时，两种选择器的**编辑粒度比预期粗**，会造成静默内容丢失：
1. `mode=replace, select_title="## 章节标题"` 会把**整个章节（含标题本身）删掉**再写入新内容 —— 若新 markdown 里没写标题行，标题就永久丢失，目录直接少一章。
2. `mode=replace, select="<单元格内文字>"` 命中表格单元格时，替换单元元是**整个块**（该格的全部行/` ` 分隔的多行）——只想改其中一行，结果把同格其它行也覆盖掉了。

两次都返回 `success: true`，不回读就发现不了。

## Root Cause

飞书 docs_ai API 的 select 匹配是**块级**的：
- `select_title` 把标题+其后到下一个同级标题的全部块视为一个可替换单元（含标题块本身）
- select 命中的一段文字所在的**最内层块**是替换单元；表格单元格内容就是一个块，` ` 只是块内软换行

调用方若按「行/段」粒度理解 select，就会低估替换范围。

## Fix

select_title 的新内容自带标题行；表格改整表重写；每次 doc_update 后 doc_fetch 回读校验；outline 查目录完整性

## Verification

某 5 万字分析报告：
- 用 `select_title="## 一、背景"` 替换章节内容（新 markdown 漏写标题）→ outline 里「一、背景」消失，回读后补 `insert-before` 恢复
- 用 select 替换表格单元格「5 台正常机的 RV…」一行 → 同格另外两行（` ` 分隔）被覆盖丢失，回读后整格重写补回
- 加上「每次改动后 `scope=outline` 校验目录」的纪律后，后续 30+ 次编辑未再丢内容

误删标题经 insert-before 补回、被覆盖单元格整格重写补回；加回读纪律后 30+ 次编辑零丢失
