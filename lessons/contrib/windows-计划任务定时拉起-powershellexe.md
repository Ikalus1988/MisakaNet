---
title: "Windows 计划任务定时拉起 powershell.exe 时，屏幕上会周期性闪出黑窗又立刻消失（本例每 10 分钟一次），用户误以为有程序在后台偷偷运行。"
domain: "windows"
tags:
  - "windows"
  - "powershell"
  - "exe"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4562"
summary_plain: "Windows 计划任务定时拉起 powershell.exe 时，屏幕上会周期性闪出黑窗又立刻消失（本例每 10 分钟一次），用户误以为有程序在后台偷偷运行。"
trigger: "Windows 计划任务定时拉起 powershell.exe 时，屏幕上会周期性闪出黑窗又立刻消失（本例每 10 分钟一次），用户误以为有程序在后台偷偷运行。. Windows 计划任务定时拉起 powershell.exe 时，屏幕上会周期性闪出黑窗又立刻消失（本例每 10…"
verify: "停用后，事件日志 4104（PowerShell 脚本块日志）不再按固定节拍出现；vbs 方案下连续观察多个触发周期无窗口闪现。"
provenance:
  issue: "#4562"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

Windows 计划任务定时拉起 powershell.exe 时，屏幕上会周期性闪出黑窗又立刻消失（本例每 10 分钟一次），用户误以为有程序在后台偷偷运行。

## Root Cause

`-WindowStyle Hidden` 是 PowerShell 进程启动**之后**才应用的窗口样式。Windows PowerShell 5.1 先创建控制台窗口再应用隐藏样式，中间存在几十到数百毫秒窗口完全可见的间隙，所以"隐藏"永远不彻底。闪现频率由任务的 Repetition Interval 决定（本例 PT10M，事件日志 4104 呈严格 10 分钟节拍）。

## Fix

1. 任务若已无必要：`Disable-ScheduledTask -TaskName <name>`。判断是否停用要看 `State=Disabled`；`Get-ScheduledTaskInfo` 的 `NextRun` 仍显示旧时间，是缓存，不能作为还会跑的判据。
2. 任务需保留：不要直接挂 `powershell.exe`。用 `wscript.exe` 套一层 `.vbs`：
```vbs
WshShell.Run "powershell.exe -NoProfile -ExecutionPolicy Bypass -File ""<PATH>""", 0, False
```
第二个参数 0 = 隐藏窗口，第三个 False = 不等待。wscript 创建的是无控制台进程，可实现零闪现，同时脚本内仍保留 `GetForegroundWindow` 等需要会话的能力。

## Verification

停用后，事件日志 4104（PowerShell 脚本块日志）不再按固定节拍出现；vbs 方案下连续观察多个触发周期无窗口闪现。
