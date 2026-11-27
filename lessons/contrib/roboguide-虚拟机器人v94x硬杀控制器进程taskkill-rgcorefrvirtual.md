---
title: "ROBOGUIDE 虚拟机器人（V9.4x）硬杀控制器进程（taskkill RGCore/frvirtual 等）后再引导，控制器进入「**冷"
domain: "fanuc"
tags:
  - "roboguide"
  - "v9"
  - "taskkill"
status: "published"
evidence_level: "E1"
created: "2026-11-27"
updated: "2026-11-27"
source: "intake-5908"
summary_plain: "ROBOGUIDE 虚拟机器人（V9.4x）硬杀控制器进程（taskkill RGCore/frvirtual 等）后再引导，控制器进入「**冷启动**」流程并弹「VARS-204 Power off…"
trigger: "ROBOGUIDE VARS-204 power off incomplete cold start RobotInit restore consumed frvirtual stuck starting"
verify: "硬杀→引导复现：VARS-204 + 首开配置链 + 仿真器「正在启动」卡死、frvirtual 不出现。改名挂起 RobotInit 后引导：仿真器可进入启动流程（状态窗从异常弹窗变为「正在启动虚拟机器人仿真器…」）；配合走完首开配置问答后控制器恢复正常服务（services.txt 重现、COM/RPC 可连）。 hard-kill + reboot reproduces VARS-204…"
provenance:
  issue: "#5908"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

ROBOGUIDE 虚拟机器人（V9.4x）硬杀控制器进程（taskkill RGCore/frvirtual 等）后再引导，控制器进入「**冷启动**」流程并弹「VARS-204 Power off incomplete」：首次开机配置链（FSSB 配置/轴号/焊接 SPOT CONFIG 表 1/62）重跑，且**虚拟机器人仿真器卡在「正在启动…」永不就绪**（此前弹 frmVirtualStartup「Unknown exception」），frvirtual 进程不出现、services.txt 不再生成、所有运动/网络通道死绝。

## Root Cause

两层叠加：
1. **硬杀=非正常断电** → 控制器持久「Power off incomplete」状态 → 每次引导走冷启动恢复链；
2. **冷启动的恢复集（workcell 下 RobotInit\Robot_1）是单次消耗品**：每次冷启动都会把恢复集搬空，而楔死/中止的引导会「边楔边吞」——重试前恢复集已被吞成残集，恢复步骤崩溃（frmVirtualStartup 异常），虚拟仿真器起不来。
另注：本故障极易误诊为「over-travel 卡死/死区」或「deadman 未合」——报警面（SRVO-003/SYST-042 等）确实会给出这类表象，但那是冷启动未完成的下游症状。更正此前一条同表象经验（MCTL-003/限位边缘）的诊断层：限位边缘只是触发器之一，恢复卡死的主体是冷启动恢复链。

## Fix

1. **预防**：关控制器走 GUI 正常退出（提示「不会保存工作单元更改」照点是），别硬杀；硬杀留下的 Power off incomplete 是一切的源头。
2. **恢复（已实证）**：把 workcell 的 `RobotInit` 目录**改名挂起**（可逆）后引导——跳过已残的恢复集，虚拟仿真器可重新启动（另一台机实证「改名后 FRVIRT 立刻首活」）。
3. 恢复集要复用时须从备份（如 RobotInit_bak）**重灌**——它是消耗品。
4. 诊断判据：看「虚拟机器人状态」窗（frmVirtualStartup）+ VARS-204 + 是否有 services.txt 生成；frvirtual 进程不在 + services.txt 不更新 = 恢复链没走完。

## Verification

硬杀→引导复现：VARS-204 + 首开配置链 + 仿真器「正在启动」卡死、frvirtual 不出现。改名挂起 RobotInit 后引导：仿真器可进入启动流程（状态窗从异常弹窗变为「正在启动虚拟机器人仿真器…」）；配合走完首开配置问答后控制器恢复正常服务（services.txt 重现、COM/RPC 可连）。

hard-kill + reboot reproduces VARS-204 + wedged sim startup with missing frvirtual; renaming RobotInit aside restores the simulator startup path (verified on one workcell, second workcell in progress)
