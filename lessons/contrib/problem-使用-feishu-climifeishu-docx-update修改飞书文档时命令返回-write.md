---
title: "feishu CLI docx update 返回 write_error not found 但内容已写入：盲目重试会重复插入"
domain: "feishu"
tags:
  - "problem"
  - "feishu"
  - "cli"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4084"
summary_plain: "使用 feishu CLI（@mi/feishu docx update）修改飞书文档时，命令返回 `write_error: \"not found\"`（code 1770002，category unknown），看似写入失败；但事后…"
trigger: "Problem 使用 feishu CLI（@mi/feishu docx update）修改飞书文档时，命令返回 `write_error: \"not fou. 使用 feishu CLI（@mi/feishu docx update）修改飞书文档时，命令返回 `write_error: \"not…"
verify: "对同一文档执行 update 后收到该错误，`feishu fetch` 显示目标段落已存在（特征字符串可检索到）且大纲中标题正常；不重试即无重复块。反例实测：对返回 \"not found\" 的 insert-after 直接重试产生了重复段落，需 delete-blocks 清理。标题写入后用 `feishu fetch --scope outline` 确认出现在大纲中即为真标题块；导出…"
provenance:
  issue: "#4084"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

使用 feishu CLI（@mi/feishu docx update）修改飞书文档时，命令返回 `write_error: "not found"`（code 1770002，category unknown），看似写入失败；但事后 fetch 验证内容实际已写入成功。若按报错盲目重试（尤其 insert 类操作），会产生重复内容。另外 `--mode insert-after` 写入含 `### 标题` 的 markdown 时，标题会被转义成字面文本（导出显示 `\###`），不会成为真标题块。

## Root Cause

1. 1770002 "not found" 是写入后校验/回读阶段的误报：块已成功写入，但回读匹配失败返回错误，错误响应与实际文档状态不一致（false negative）。
2. insert 路径不解析 markdown 标题语法（`replace` 路径才解析），`###` 被当普通文本写入。

## Fix

1. 收到 1770002 "not found" 时不要直接重试：先 `feishu fetch <token>`（或 `--scope outline`）核对内容是否已写入；确认已写入则不再重试。仅当确认未写入时才重试，且重试前再次核对，避免重复插入。
2. 新增带标题的小节时用 `--mode replace --select-title` 锚定相邻章节重写（内容中带上新小节），不要用 `insert-after` 传含 `#` 的 markdown；如已产生转义标题文本块，用 `feishu docx delete-blocks <doc> <block_id,...>` 按块 ID 精准删除重复部分。

## Verification

对同一文档执行 update 后收到该错误，`feishu fetch` 显示目标段落已存在（特征字符串可检索到）且大纲中标题正常；不重试即无重复块。反例实测：对返回 "not found" 的 insert-after 直接重试产生了重复段落，需 delete-blocks 清理。标题写入后用 `feishu fetch --scope outline` 确认出现在大纲中即为真标题块；导出 markdown 中出现 `\###` 字面转义即为失败写法。
