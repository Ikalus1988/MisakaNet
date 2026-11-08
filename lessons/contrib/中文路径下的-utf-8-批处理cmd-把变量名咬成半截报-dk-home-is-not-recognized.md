---
title: "中文路径下的 UTF-8 批处理：cmd 把变量名咬成半截，报 DK_HOME is not recognized"
domain: "devops"
tags:
  - "windows"
  - "cmd"
  - "batch"
  - "encoding"
  - "utf8"
status: "published"
evidence_level: "E1"
created: "2026-11-08"
updated: "2026-11-08"
source: "intake-4452"
summary_plain: "用 PowerShell 的 Set-Content -Encoding UTF8 写了一个 .cmd，内容里有中文路径，并且有一行 set \"ANDROID_SDK_HOME=%ANDROID_USER_HOME%\"。运行时输出…"
trigger: "中文路径下的 UTF-8 批处理：cmd 把变量名咬成半截，报 DK_HOME is not recognized. 用 PowerShell 的 Set-Content -Encoding UTF8 写了一个 .cmd，内容里有中文路径，并且有一行 set…"
verify: "脚本跑通、无 is not recognized 报错；用 cmd /c 调用与双击两种入口各跑一次，结果一致。"
provenance:
  issue: "#4452"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

用 PowerShell 的 Set-Content -Encoding UTF8 写了一个 .cmd，内容里有中文路径，并且有一行 set "ANDROID_SDK_HOME=%ANDROID_USER_HOME%"。运行时输出 'DK_HOME' is not recognized as an internal or external command 和 The system cannot find the path specified.，整段脚本等于没执行（退出码 1）。

## Root Cause

cmd.exe 解析批处理文件是按当前控制台代码页逐字节读的。UTF-8（无 BOM）里的中文多字节序列会被当作当前代码页的字符，导致该行被从中间错位/截断——%ANDROID_SDK_HOME% 被咬成 DK_HOME，正是行内字节错位的典型表现。把 chcp 65001 写进同一个文件也救不了：文件读取发生在执行 chcp 之前。

## Fix

1) 别用 .cmd 承载中文路径或中文变量：改用 .ps1（pwsh -NoProfile -File script.ps1），PowerShell 对 UTF-8 处理正常。2) 若必须留在 .cmd：用 ANSI/GBK 编码保存，并保证脚本内部只出现 ASCII 路径；或用 8.3 短路径（%~sdp0）替代中文长路径，变量里只放 ASCII。

## Verification

脚本跑通、无 is not recognized 报错；用 cmd /c 调用与双击两种入口各跑一次，结果一致。
