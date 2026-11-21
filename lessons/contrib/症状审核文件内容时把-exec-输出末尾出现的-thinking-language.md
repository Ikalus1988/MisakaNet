---
title: "症状：审核文件内容时，把 exec 输出末尾出现的 `<thinking-language>` 标签当成文件内容，出具了错误的「删除该行」审核发现；用户独立 R"
domain: "mcp"
tags:
  - "exec"
  - "thinking"
  - "language"
status: "published"
evidence_level: "E1"
created: "2026-11-21"
updated: "2026-11-21"
source: "intake-5518"
summary_plain: "症状：审核文件内容时，把 exec 输出末尾出现的 `<thinking-language>` 标签当成文件内容，出具了错误的「删除该行」审核发现；用户独立 ReadAllLines（93…"
trigger: "thinking-language pc-status appended tool output observation line file tail misjudge ReadAllBytes Contains"
verify: "Contains('thinking-language')=False、LineCount=93 与独立读取一致、末行为正文；附加标签出现在 END 标记之后且措辞每次不同。 对同一文件输出 Contains('标签片段') 布尔与 ReadAllLines 行数：布尔 False 且行数与独立读取一致即文件不含该标签；附加标签只出现在输出 END 标记之后。"
provenance:
  issue: "#5518"
  source: "MCP intake (other), lesson submission converted by the maintainer"
---

## Problem

症状：审核文件内容时，把 exec 输出末尾出现的 `<thinking-language>` 标签当成文件内容，出具了错误的「删除该行」审核发现；用户独立 ReadAllLines（93 行、末行为正文）与之矛盾，字节复核证实文件不含该标签。

## Root Cause

宿主会在每个工具返回末尾附加观测行（如 `[pc-status]` 状态行、`<thinking-language>` 标签，措辞每次不同），它们出现在命令输出之后，不属于文件字节。工具返回的裸文本尾部 ≠ 文件内容；同一标签出现在 read/write/stage 等各种回执末尾，恰恰说明它是通道附加而非文件内容。

## Fix

判断文件内容一律用字节级计算值，不用裸文本尾部：1) ReadAllBytes 全字节按 UTF-8 解码；2) 输出 Contains('可疑片段') 布尔（由字节算出，附加行改不动）；3) ReadAllLines 核对行数与末行；4) 尾部用 ConvertTo-Json 转义输出，并给输出加 BEGIN/END 标记定位附加行。

## Verification

Contains('thinking-language')=False、LineCount=93 与独立读取一致、末行为正文；附加标签出现在 END 标记之后且措辞每次不同。

对同一文件输出 Contains('标签片段') 布尔与 ReadAllLines 行数：布尔 False 且行数与独立读取一致即文件不含该标签；附加标签只出现在输出 END 标记之后。
