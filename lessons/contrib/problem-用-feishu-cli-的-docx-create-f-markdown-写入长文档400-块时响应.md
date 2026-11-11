---
title: "feishu docx create 长文档（400+ 块）降级纯文本：Markdown convert API failed"
domain: "feishu"
tags:
  - "problem"
  - "feishu"
  - "cli"
status: "published"
evidence_level: "E1"
created: "2026-11-11"
updated: "2026-11-11"
source: "intake-4682"
summary_plain: "feishu docx create 长文档（400+ 块）降级纯文本：Markdown convert API failed"
trigger: "feishu docx create 长文档（400+ 块）降级纯文本：Markdown convert API failed"
verify: "修复后跑两个检查都过才算完： 1. `feishu docx read <doc>` 输出全文，grep 转义残留（`\\#`、`\\*` 开头的行）应为 0； 2. `feishu fetch <doc> --scope outline` 里该标题以 `## x.y` 正常出现在大纲中（假标题不会进大纲）。"
provenance:
  issue: "#4682"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

用 feishu CLI 的 `docx create -f <markdown>` 写入长文档（400+ 块）时，响应 warnings 里出现 "Markdown convert API failed, content degraded to plain text"（HTTP 400），受影响片段的 markdown 标记未被解析：标题写成字面文本 `\## 2.7 xxx`、加粗写成 `\*\*xxx\*\*`（文档正文里显示转义符）。之后用 `docx update --mode replace --select ... -c "**xxx**"` 修复：**行内加粗能修好，但标题块修不好**——替换后仍是普通文本块，`\##` 转义符原样残留。

## Root Cause

1. 写入侧：Markdown convert API 对部分片段间歇 400，CLI 降级为纯文本块插入，markdown 语法（#、**）原样入库。
2. 修复侧：docs_ai 的 str_replace 只替换文本内容、**不改变块类型**（block_type 2 文本块永远变不成 heading 块），所以 replace 无法把降级的"假标题"修成真标题。

## Fix

分两步修，先行内后块级：
1. **行内样式**（加粗/斜体被转义）：`docx update <doc> --mode replace --select '被转义的字面文本' -c '**正确markdown**'`，docs_ai 替换后即恢复行内格式。
2. **块类型错误**（假标题）：不用 replace，改用「插入真块 + 删除假块」：
   - `docx update <doc> --mode insert-before --select '<假标题块后面的段落文本>' -c '## 正确标题'`（新块由 markdown 转换生成，是真 heading 块）；
   - `feishu docx delete-block <doc> <假标题块id>`（块 id 用 `feishu docx blocks <doc>` 在输出里搜文字定位）。
3. 预防：写入后立即检查响应的 `warnings[]`；正文含多段公式/表格/代码块混排时更容易触发降级，重要内容可分段写入（`--mode append`）降低触发面。

## Verification

修复后跑两个检查都过才算完：
1. `feishu docx read <doc>` 输出全文，grep 转义残留（`\#`、`\*` 开头的行）应为 0；
2. `feishu fetch <doc> --scope outline` 里该标题以 `## x.y` 正常出现在大纲中（假标题不会进大纲）。
