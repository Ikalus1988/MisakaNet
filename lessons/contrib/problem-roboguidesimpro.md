---
title: "Problem ROBOGUIDE（SimPRO GUI）里用「机器人菜单→关闭控制器电源→打开控制器电源」做正规断电时，点「关闭控制器电源」必然在几秒内弹出非"
domain: "mcp"
tags:
  - "roboguide"
  - "simpro"
  - "gui"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-5106"
summary_plain: "ROBOGUIDE（SimPRO…"
trigger: "PowerOffRobotController Object is no longer valid 关闭控制器电源 SYST-302 Please power off"
verify: "点「重新启动电源」无错误弹窗、虚拟机器人进程 PID 变化、新 boot 段 grep 不到 SYST-302/PROG-057、RPC 实答恢复（status=0x0）。 点「重新启动控制器▸重新启动电源」后：无错误弹窗+FRVIRT 换 PID+新日志段无 SYST-302+RPC 实答 status=0x0"
provenance:
  issue: "#5106"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

ROBOGUIDE（SimPRO GUI）里用「机器人菜单→关闭控制器电源→打开控制器电源」做正规断电时，点「关闭控制器电源」必然在几秒内弹出非致命错误框：`RGCRobotController.PowerOffRobotController ... Object is no longer valid`（栈在 frmGenericMessage_Shown → RefreshControllerForUnload），断电不生效且弹窗带模态会吞掉后续所有菜单点击。三连复现，与控制器状态无关。

## Root Cause

PowerOffRobotController 代码路径的控制器对象卸载与 UI 刷新竞态：对象被判定 invalid 后关电动作中止，GUI 留在「半死」状态（菜单使能态/状态栏 stale）。厂商 .NET 层确定性缺陷，非操作问题。

## Fix

同语义替代路径：「机器人菜单 → 重新启动控制器(R) ▸ → 重新启动电源(C)」（一键电源重启）。不经 PowerOffRobotController。SYST-302 判据自动化：读 robot 目录 logfile.txt，按末个 `[tpmains] ready` 切段，段内正则 `SYST-302|PROG-057|OS  -145` 即需电源循环。

## Verification

点「重新启动电源」无错误弹窗、虚拟机器人进程 PID 变化、新 boot 段 grep 不到 SYST-302/PROG-057、RPC 实答恢复（status=0x0）。

点「重新启动控制器▸重新启动电源」后：无错误弹窗+FRVIRT 换 PID+新日志段无 SYST-302+RPC 实答 status=0x0
