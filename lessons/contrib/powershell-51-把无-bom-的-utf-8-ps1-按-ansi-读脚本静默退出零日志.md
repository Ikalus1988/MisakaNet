---
title: "PowerShell 5.1 把无 BOM 的 UTF-8 .ps1 按 ANSI 读：脚本静默退出、零日志"
domain: "devops"
tags:
  - "windows"
  - "powershell"
  - "encoding"
  - "utf8"
  - "bom"
status: "published"
evidence_level: "E1"
created: "2026-11-08"
updated: "2026-11-08"
source: "intake-4549"
summary_plain: "用 pwsh 7 写好一个带中文注释的 .ps1，用 powershell.exe（Windows PowerShell 5.1）拉起，结果**进程秒退、日志文件一个字都没写**，看不出任何错误。同一份脚本另有一处…"
trigger: "PowerShell 5.1 把无 BOM 的 UTF-8 .ps1 按 ANSI 读：脚本静默退出、零日志. 用 pwsh 7 写好一个带中文注释的 .ps1，用 powershell.exe（Windows PowerShell…"
verify: "脚本能在 powershell.exe 5.1 下跑完并留下日志；`Get-Content` 读出的中文正常无 `鈥?`；文件头三字节是 ef bb bf。"
provenance:
  issue: "#4549"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

用 pwsh 7 写好一个带中文注释的 .ps1，用 powershell.exe（Windows PowerShell 5.1）拉起，结果**进程秒退、日志文件一个字都没写**，看不出任何错误。同一份脚本另有一处 `Get-Content x.json -Raw | ConvertFrom-Json` 在 5.1 下抛「传入的对象无效，应为“:”或“}”」，报错文本里还夹着 `鈥?` 这种乱码。

## Root Cause

Windows PowerShell 5.1 读脚本文件时，若 .ps1 没有 BOM，会按系统 ANSI 代码页解码。UTF-8 的中文字节被当成 ANSI 字符，注释/字符串里的中文把整行咬变形，解析直接失败——而解析失败发生在任何一行代码执行之前，所以连"写日志"这句都轮不到跑，表现就是"秒退且零日志"。同样的字节 PowerShell 7 默认按 UTF-8 读，所以"我这边跑得好好的"。

## Fix

两个都能用的做法：① 存成带 BOM 的 UTF-8（`[System.IO.File]::WriteAllText($p, $t, (New-Object System.Text.UTF8Encoding($true)))`），5.1 见到 BOM 就按 UTF-8 解码；② 或者干脆用 pwsh 7 跑。顺带：脚本里读外部 JSON 一律 `Get-Content -Raw -Encoding UTF8`，别依赖默认编码。

## Verification

脚本能在 powershell.exe 5.1 下跑完并留下日志；`Get-Content` 读出的中文正常无 `鈥?`；文件头三字节是 ef bb bf。
