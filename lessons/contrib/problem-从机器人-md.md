---
title: "ROBOGUIDE 版本代差：备份与媒体版本不一致时变量恢复违例、FTP 550、虚拟机器人起不来"
domain: "mcp"
tags:
  - "problem"
  - "md"
  - "roboguide"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4522"
summary_plain: "从机器人 MD: 文件备份还原/重建虚拟机器人（ROBOGUIDE/FRVRC）时，若备份的控制器软件版本与本机 FRVRC/媒体版本不一致（例：备份=V9.40P/38 Build 9.40229，本机媒体=V9.40P/29…"
trigger: "Problem 从机器人 MD: 文件备份还原/重建虚拟机器人（ROBOGUIDE/FRVRC）时，若备份的控制器软件版本与本机 FRVRC/媒体版本不一致（例. 从机器人 MD: 文件备份还原/重建虚拟机器人（ROBOGUIDE/FRVRC）时，若备份的控制器软件版本与本机…"
verify: "本机实测三症状同现且三方对表结果一致（备份 P/38 vs banner P/29）；将同一备份走 from-backup 向导路径的行为差异可复现对比。修复后验证待匹配版本组件到位后进行（诊断判据已可重复执行）。 summary.dg+backdate.dt vs FTP banner+version.ht 对表判据可重复"
provenance:
  issue: "#4522"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

从机器人 MD: 文件备份还原/重建虚拟机器人（ROBOGUIDE/FRVRC）时，若备份的控制器软件版本与本机 FRVRC/媒体版本不一致（例：备份=V9.40P/38 Build 9.40229，本机媒体=V9.40P/29 Build 9.40179），会出现三症状：①启动期 .sv 变量恢复阶段 Memory access violation（frmVirtualStartup 面板 6553601）；②FTP 上传 .tp 报 `550 Prog uses un-installed option`（程序在新版本编译、旧版本校验器不认）；③vmgr/vmsvcpy 日志 dimension mismatch（数组维度不重分配）。三症状易被误诊为内存配置、选项安装、注入落点三个独立问题（本会话即误诊三轮）。

## Root Cause

控制器软件版本代差：备份文件（.sv/.tp）携带源版本的变量布局/指令选项位，旧版 FRVRC 引导的控制器无法正确恢复/校验。相关已知课：roboguide-reinstall-missing-frvrc-controller-version（缺 FRVRC 版本工位打不开）——本条是其「版本不匹配但能启动」的姊妹场景。

## Fix

三方版本对表定位法；安装匹配 FRVRC/媒体或走 frcreatevirtualrobot from-backup 向导

## Verification

本机实测三症状同现且三方对表结果一致（备份 P/38 vs banner P/29）；将同一备份走 from-backup 向导路径的行为差异可复现对比。修复后验证待匹配版本组件到位后进行（诊断判据已可重复执行）。

summary.dg+backdate.dt vs FTP banner+version.ht 对表判据可重复
