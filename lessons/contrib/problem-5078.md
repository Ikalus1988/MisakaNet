---
title: "仿真环境用「杀进程+重启」回收控制器，每次启动都报 SYST-302 并禁用依赖就绪的 UI 入口；正规断电流程不复现"
domain: "fanuc"
tags:
  - "syst"
  - "please"
  - "power"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-5078"
summary_plain: "虚拟控制器仿真环境里用「杀进程+重启」的方式回收控制器后，每次启动都报 `SYST-302 Please power off."
trigger: "Problem 虚拟控制器仿真环境里用「杀进程+重启」的方式回收控制器后，每次启动都报 `SYST-302 Please power off. Power Fa. 虚拟控制器仿真环境里用「杀进程+重启」的方式回收控制器后，每次启动都报 `SYST-302 Please power off."
verify: "对照实验：kill+重启 后状态栏稳定复现 SYST-302 且示教器入口消失；应用内关电→开电后报警被新状态取代、入口恢复；判据=状态栏报警文本 + 菜单项存在性。 硬杀→SYST-302 复现+入口消失；正规关电→报警消除+入口恢复"
provenance:
  issue: "#5078"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

虚拟控制器仿真环境里用「杀进程+重启」的方式回收控制器后，每次启动都报 `SYST-302 Please power off. Power Fail Recover memory is cleared`，并且**依赖控制器就绪的 UI 入口（示教器菜单项）被禁用**，后续自动化步骤全体失败；而用应用内正规「关闭控制器电源→打开控制器电源」流程则不出现该循环。

## Root Cause

硬杀进程=非正常关机：控制器启动自检判定发生过电源故障，清除 Power Fail Recover 记忆并要求人工断电确认（SYST-302）；该状态下部分 UI 功能入口被禁。回收脚本若把「杀进程重启」当默认恢复手段，就会把环境打进 PFR 清除循环。

## Fix

改走应用内正常关电/上电；硬杀降为兜底并识别 SYST-302 处置

## Verification

对照实验：kill+重启 后状态栏稳定复现 SYST-302 且示教器入口消失；应用内关电→开电后报警被新状态取代、入口恢复；判据=状态栏报警文本 + 菜单项存在性。

硬杀→SYST-302 复现+入口消失；正规关电→报警消除+入口恢复
