---
title: "FANUC ROBOGUIDE V9.40「folder-mode 恢复/注入失效」是假阴性：恢复导入要跑几分钟，引导后立刻查 MD: 会看到 404/模板内容"
domain: "fanuc"
tags:
  - "fanuc"
  - "roboguide"
  - "v9"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-5019"
summary_plain: "FANUC ROBOGUIDE V9.40「folder-mode 恢复/注入失效」是假阴性：恢复导入要跑几分钟，引导后立刻查 MD: 会看到 404/模板内容，误判为「没生效」。"
trigger: "FANUC ROBOGUIDE V9.40「folder-mode 恢复/注入失效」是假阴性：恢复导入要跑几分钟，引导后立刻查 MD: 会看到 404/模板内容. 误判为「没生效」。"
verify: "恢复源放 20 个标记文件（含不同扩展名）→ 冷启动 → 每 30s 探 `GET /MD/<file>` → 全部 200 且 `RobotInit\\Robot_1` 清空 = 导入成功。任一文件长时间 404 才是真缺失。 实测…"
provenance:
  issue: "#5019"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

FANUC ROBOGUIDE V9.40「folder-mode 恢复/注入失效」是假阴性：恢复导入要跑几分钟，引导后立刻查 MD: 会看到 404/模板内容，误判为「没生效」。

## Root Cause

恢复导入是**慢过程**：引导完成（services.txt 重写）≠ 导入完成。实测动态证据链——
引导后第 1 分钟探针：`PANEL*.DT`=200（导入序靠前）但 `ORDERFIL.DAT`<PATH>`=404；
数分钟后同一批 20/20 全部 200。**导入分批进行，判据查得太早必得假阴性。**
另：恢复源是单次消耗品——每次引导（哪怕随后楔死）都会把 `RobotInit\Robot_1` 搬空，重试前必须重灌。

## Fix

判据改成**动态对照**，不要单点快照：
1. 引导后等 `RobotInit\Robot_1` 被搬空（消费完成信号）再探；
2. 或间隔 30-60s 两次探同一批文件，看 404→200 迁移；
3. 别在导入未完成时下「失效」结论；本机引导常需 5-7 分钟（负载重），给足窗口再判「引导卡死」。

## Verification

恢复源放 20 个标记文件（含不同扩展名）→ 冷启动 → 每 30s 探 `GET /MD/<file>` →
全部 200 且 `RobotInit\Robot_1` 清空 = 导入成功。任一文件长时间 404 才是真缺失。
实测 20/20（ORDERFIL.DAT/AAVM*.VR/HTTPKCL.VR/SYSVARS.SV/PROBE10.HTM/FLEXUIF.XML/PANEL1-4.DT/GETDATA.TP 等）全绿。

20 个标记文件冷启动后全部 GET /MD/ 200 + RobotInit/Robot_1 清空（实测 20/20）
