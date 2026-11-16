---
title: "在 PowerShell 里用内联方式把 Python 脚本传给解释器（如 `python -c \"...\"`、here-string 或管道），脚本里的单引号"
domain: "windows"
tags:
  - "python"
  - "count"
  - "powershell"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-5070"
summary_plain: "在 PowerShell 里用内联方式把 Python 脚本传给解释器（如 `python -c \"...\"`、here-string 或管道），脚本里的单引号/双引号被 PowerShell 剥掉或改写，Python 端报…"
trigger: "在 PowerShell 里用内联方式把 Python 脚本传给解释器（如 `python -c \"...\"`、here-string 或管道），脚本里的单引号. 双引号被 PowerShell 剥掉或改写，Python 端报 SyntaxError（unterminated string…"
verify: "同样代码以 .py 文件形式运行退出码 0 且输出正确；内联方式复现报错（对照实验）。"
provenance:
  issue: "#5070"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

在 PowerShell 里用内联方式把 Python 脚本传给解释器（如 `python -c "..."`、here-string 或管道），脚本里的单引号/双引号被 PowerShell 剥掉或改写，Python 端报 SyntaxError（unterminated string literal），同一段脚本写成 .py 文件执行却正常。

## Root Cause

PowerShell 在构造命令行时对引号的解析与 Python 词法不一致：内层引号（尤其 SQL 里的 '...' 与 `*`、`count(*)` 等）会被 PS 展开或吞掉；且每次引号嵌套层数不同，坏的位置时好时坏（同一天坏 4 次）。

## Fix

不要内联：把 Python 代码写成 .py 文件（UTF-8），用解释器完整路径 + `-X utf8` 执行；一次性的临时脚本用完可删。需要传参时用 argv 而非字符串拼接。

## Verification

同样代码以 .py 文件形式运行退出码 0 且输出正确；内联方式复现报错（对照实验）。
