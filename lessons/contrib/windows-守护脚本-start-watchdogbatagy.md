---
title: "Windows 守护脚本 `start-watchdog.bat`（agy-watchdog）直接双击/命令行启动时报「已在运行中 (PID: 28096)，跳"
domain: "windows"
tags:
  - "start-watchdog.bat"
  - "powershell.exe"
  - "watchdog-daemon.ps1"
status: "published"
evidence_level: "E1"
created: "2026-11-28"
updated: "2026-11-28"
source: "intake-5932"
summary_plain: "Windows 守护脚本 `start-watchdog.bat`（agy-watchdog）直接双击/命令行启动时报「已在运行中 (PID: 28096)，跳过重复启动」，但任务管理器里根本没有 watchdog-daemon.ps1…"
trigger: "start-watchdog.bat 报已在运行中 但进程不存在 WMI CommandLine 自匹配 powershell -Command 内联"
verify: "启动后 `state\\daemon.pid` 写入新 PID 且 `Get-Process -Id <pid>` 存在；日志出现 `daemon started (PID=…)`；停止守护后再次启动能正常起（不再报已在运行）。 daemon.pid 写入新 PID 且 Get-Process 存在，日志出现 daemon started (PID=…)"
provenance:
  issue: "#5932"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

Windows 守护脚本 `start-watchdog.bat`（agy-watchdog）直接双击/命令行启动时报「已在运行中 (PID: 28096)，跳过重复启动」，但任务管理器里根本没有 watchdog-daemon.ps1 进程，守护其实没起来；`state\daemon.pid` 里存的是早已退出的 PID 21568。

## Root Cause

bat 用 `powershell.exe -Command "<整段脚本内联>"` 启动守护，判断「是否已在运行」用的是 WMI 扫描：
`Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" | Where-Object CommandLine -like '*watchdog-daemon.ps1*'`
被扫描的 powershell 命令行里本身就包含 `watchdog-daemon.ps1` 字符串（因为整段脚本内联在命令行里），于是把自己算了进去 → 自匹配，误判「已在运行」。同一条 bat 在其它机器偶发正常，取决于命令行长度/引号形式。

## Fix

不要让守护脚本以 `-Command` 内联方式出现自己的名字，改用 `-File` 直接执行脚本文件：
`Start-Process -FilePath powershell.exe -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-WindowStyle','Hidden','-STA','-File','<PATH>')`
判活逻辑同时加排除：跳过 `$PID` 与父进程链，或改用「读 daemon.pid → Get-Process 验证」而不是扫命令行。

## Verification

启动后 `state\daemon.pid` 写入新 PID 且 `Get-Process -Id <pid>` 存在；日志出现 `daemon started (PID=…)`；停止守护后再次启动能正常起（不再报已在运行）。

daemon.pid 写入新 PID 且 Get-Process 存在，日志出现 daemon started (PID=…)
