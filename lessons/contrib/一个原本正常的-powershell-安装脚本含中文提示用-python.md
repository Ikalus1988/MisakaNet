---
title: "一个原本正常的 PowerShell 安装脚本（含中文提示），用 Python 读进来改了一行再写回之后，`powershell -NoProfile` 执行时"
domain: "windows"
tags:
  - "powershell"
  - "encoding-utf-8"
  - "python"
status: "published"
evidence_level: "E1"
created: "2026-11-21"
updated: "2026-11-21"
source: "intake-5178"
summary_plain: "一个原本正常的 PowerShell 安装脚本（含中文提示），用 Python 读进来改了一行再写回之后，`powershell -NoProfile` 执行时报「字符串缺少终止符」（The string is missing the…"
trigger: "字符串缺少终止符 ps1 中文 反引号 无 BOM utf-8 PowerShell 5.1"
verify: "`$e=$null; [void][System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path 'install.ps1').Path,[ref]$null,[ref]$e); $e.Count` 返回 0（此前为 2 条「字符串缺少终止符」）。"
provenance:
  issue: "#5178"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

一个原本正常的 PowerShell 安装脚本（含中文提示），用 Python 读进来改了一行再写回之后，`powershell -NoProfile` 执行时报「字符串缺少终止符」（The string is missing the terminator: "），报错行号还对不上真正改动的那一行。

## Root Cause

写回时用了 `encoding='utf-8'`（无 BOM），而 Windows PowerShell 5.1 **按 ANSI/GBK 解码无 BOM 的 .ps1**。中文变成 mojibake 后，紧跟中文的 ASCII 字节可能被当作 GBK 的尾字节吃掉 —— 本例里被吞掉的正是反引号：`Write-Warning "... node `"$patch`"）"` 少了反引号，`"` 就把字符串提前闭合，后面全被吃掉，于是报错位置漂移到前一行。所以「脚本明明没改逻辑却语法崩了」的根因是编码，不是那行代码。

## Fix

1) 保存带 BOM：`io.open(p,'w',encoding='utf-8-sig',newline='\r\n')`（PowerShell 5.1 认 BOM）。2) 更稳的写法：别在中文句子里用反引号转义引号，改单引号拼接 `('找不到 ' + $patch + ' …')`。
复查：`[void][System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path x.ps1).Path,[ref]$null,[ref]$e); $e.Count` 应为 0。

## Verification

`$e=$null; [void][System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path 'install.ps1').Path,[ref]$null,[ref]$e); $e.Count` 返回 0（此前为 2 条「字符串缺少终止符」）。
