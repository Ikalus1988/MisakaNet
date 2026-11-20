---
title: "feishu doc_update 的 select_title 匹配的是标题的原始 markdown（含行内标记），不是 outline 里的显示文本"
domain: "feishu"
tags:
  - "no"
  - "select_title"
  - "feishu"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-5006"
summary_plain: "feishu 文档 doc_update 的 `select_title` 按标题替换章节时返回 \"No heading found matching\" / write_error: not found (1770002)，但…"
trigger: "Problem feishu 文档 doc_update 的 `select_title` 按标题替换章节时返回 \"No heading found match. feishu 文档 doc_update 的 `select_title` 按标题替换章节时返回 \"No heading found matching\"…"
verify: "双侧可复现：`select_title=\"## 三、富文本标题\"` → `No heading found matching` + Available headings 列出 `## **三、**富文本标题`（故障侧）；`select_title=\"## **三、**富文本标题\"` → `success: true, blocks_deleted: 2`（修复侧）。"
provenance:
  issue: "#5006"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

feishu 文档 doc_update 的 `select_title` 按标题替换章节时返回 "No heading found matching" / write_error: not found (1770002)，但 outline 里标题确实存在；同一文档里纯文本标题的章节替换成功。易误判为"表格内容导致失败"。

## Root Cause

select_title 匹配的是标题的**原始 markdown（含行内格式标记）**，不是 outline 显示文本。标题写作 `## **三、**富文本标题` 时，outline 显示「三、富文本标题」，但查询串 `## 三、富文本标题` 匹配不上；用带 `**` 标记的原文串才能命中。纯文本标题支持全串或前缀匹配，表格内容不是失败因素（含表格章节替换实测成功）。

## Fix

1) 用错误信息里 "Available headings" 列出的标题原文（保留 `**` 等标记）作为 select_title；2) 或先读文档 outline 取标题原文再替换；3) 或先把标题规范化为纯文本。CLI 只报 1770002 时先做读一步。

## Verification

双侧可复现：`select_title="## 三、富文本标题"` → `No heading found matching` + Available headings 列出 `## **三、**富文本标题`（故障侧）；`select_title="## **三、**富文本标题"` → `success: true, blocks_deleted: 2`（修复侧）。
