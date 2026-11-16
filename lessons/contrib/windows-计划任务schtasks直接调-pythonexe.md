---
title: "Windows 计划任务（schtasks）直接调 python.exe 跑脚本，每次触发会闪出一个黑色控制台窗口，干扰正在使用桌面的用户。 Root Caus"
domain: "windows"
tags:
  - "wscript.exe"
  - "windows"
  - "schtasks"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-5071"
summary_plain: "Windows 计划任务（schtasks）直接调 python.exe 跑脚本，每次触发会闪出一个黑色控制台窗口，干扰正在使用桌面的用户。"
trigger: "Windows 计划任务（schtasks）直接调 python.exe 跑脚本，每次触发会闪出一个黑色控制台窗口，干扰正在使用桌面的用户。 Root Caus. Windows 计划任务（schtasks）直接调 python.exe 跑脚本，每次触发会闪出一个黑色控制台窗口，干扰正在使用桌面的用户。"
verify: "手动触发一次任务，桌面上不再出现控制台窗口；任务结果码仍为 0、产出文件正常增长。"
provenance:
  issue: "#5071"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

Windows 计划任务（schtasks）直接调 python.exe 跑脚本，每次触发会闪出一个黑色控制台窗口，干扰正在使用桌面的用户。

## Root Cause

计划任务默认以交互式方式启动控制台程序，python.exe 是控制台应用，运行时会创建可见的 conhost 窗口。

## Fix

1. 用 wscript.exe 包一层无窗口 VBS 启动（`wscript.exe run_hidden.vbs your.cmd`），VBS 里用 0 隐藏窗口；
2. 或启动器脚本里对 subprocess 传 `CREATE_NO_WINDOW`（0x08000000）标志；
3. 任务属性里勾选「不管用户是否登录都要运行」也能在部分场景去掉交互窗口。

## Verification

手动触发一次任务，桌面上不再出现控制台窗口；任务结果码仍为 0、产出文件正常增长。
