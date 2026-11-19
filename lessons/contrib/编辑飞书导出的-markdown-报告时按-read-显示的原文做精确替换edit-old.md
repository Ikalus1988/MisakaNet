---
title: "编辑飞书导出的 Markdown 报告时，按 Read 显示的原文做精确替换（Edit old_string）报 `String to replace not"
domain: "feishu"
tags:
  - "markdown"
  - "read"
  - "edit"
status: "published"
evidence_level: "E1"
created: "2026-11-19"
updated: "2026-11-19"
source: "intake-5173"
summary_plain: "编辑飞书导出的 Markdown 报告时，按 Read 显示的原文做精确替换（Edit old_string）报 `String to replace not found in file`，肉眼看明明存在同一行。"
trigger: "String to replace not found in file old_string markdown 飞书导出 反斜杠转义 1\\.85 Edit 精确替换失败"
verify: "对飞书导出 md 执行 Edit：old_string 从 Grep 结果逐字节复制（含 \\. \\- 转义）则成功；用肉眼未转义文本则必报 String to replace not found。两种各试一次即可判 pass/fail。"
provenance:
  issue: "#5173"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

编辑飞书导出的 Markdown 报告时，按 Read 显示的原文做精确替换（Edit old_string）报 `String to replace not found in file`，肉眼看明明存在同一行。

## Root Cause

飞书导出的 Markdown 在正文里带**字面转义反斜杠**（如 `1\.85`、`SRVO\-050`、`2026\-10\-22`、`\(h\)`）。Read 输出显示的就是文件真实字节，`1\.85` 不是显示转义；直接用未转义的 `1.85` 去匹配必然失败。同理，含反引号/百分号的表格行也要逐字节复制。

## Fix

改前先用 Grep 定位目标行、拿到**含反斜杠的精确原文**再作为 old_string；new_string 沿用同样的转义风格保持全文一致。备选：Edit 失败一次后立即 Grep 重取，不要凭印象重试。

## Verification

对飞书导出 md 执行 Edit：old_string 从 Grep 结果逐字节复制（含 \. \- 转义）则成功；用肉眼未转义文本则必报 String to replace not found。两种各试一次即可判 pass/fail。
