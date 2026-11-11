---
title: "双击 .ps1 不会执行：交付\"双击运行\"的脚本给用户，可能一条都没跑"
domain: "devops"
tags:
  - "powershell"
  - "windows"
  - "file-association"
  - "delivery"
  - "ux"
status: "published"
evidence_level: "E1"
created: "2026-11-11"
updated: "2026-11-11"
source: "intake-4624"
summary_plain: "给用户一个 PowerShell 更新脚本，附言\"关掉目标程序后双击这个文件\"。用户照做，回来反馈\"有的更新好了、有的没有\"。实际检查：脚本自己写的日志文件根本不存在，所有目标包的版本仍是旧的——脚本一次都没执行过。"
trigger: "双击 .ps1 不会执行：交付\"双击运行\"的脚本给用户，可能一条都没跑. 给用户一个 PowerShell…"
verify: "双击后 30 秒内，日志文件应出现第一行记录；没有日志 = 脚本没执行，此时不要问\"哪里失败了\"，先确认它跑没跑。"
provenance:
  issue: "#4624"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

给用户一个 PowerShell 更新脚本，附言"关掉目标程序后双击这个文件"。用户照做，回来反馈"有的更新好了、有的没有"。实际检查：脚本自己写的日志文件根本不存在，所有目标包的版本仍是旧的——脚本一次都没执行过。

## Root Cause

Windows 对 .ps1 的默认文件关联是"用编辑器打开"（记事本/IDE），不是执行。双击只会打开一个显示源码的窗口，脚本一行都不会跑；用户看到有窗口弹出来，很容易以为已经跑了。另外即使关联到 run，默认 ExecutionPolicy 也会拦住未签名脚本。

## Fix

交付"要给非命令行用户用的脚本"时，别只给 .ps1：
1) 建一个 .lnk 快捷方式：TargetPath 设 powershell.exe，Arguments 设 -NoProfile -ExecutionPolicy Bypass -File "<脚本路径>"，双击它才真跑；
2) 或在说明里明确写"右键 → 使用 PowerShell 运行"；
3) 脚本第一行就写日志（Out-File -Append），把"有没有真的启动"变成可观测事实，而不是靠用户回忆。

## Verification

双击后 30 秒内，日志文件应出现第一行记录；没有日志 = 脚本没执行，此时不要问"哪里失败了"，先确认它跑没跑。
