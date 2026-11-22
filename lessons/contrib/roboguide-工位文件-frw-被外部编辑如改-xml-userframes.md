---
title: "ROBOGUIDE 工位文件 .frw 被外部编辑（如改 XML UserFrames 坐标）后，该工位每次引导必楔死：RGCore 存活但冻在 frmSpla"
domain: "fanuc"
tags:
  - "roboguide"
  - "frw"
  - "xml"
status: "published"
evidence_level: "E1"
created: "2026-11-22"
updated: "2026-11-22"
source: "intake-5563"
summary_plain: "ROBOGUIDE 工位文件 .frw 被外部编辑（如改 XML UserFrames 坐标）后，该工位每次引导必楔死：RGCore 存活但冻在…"
trigger: "ROBOGUIDE .frw 外部编辑 校验和 工作单元文件的校验与不正确 frmSplash 楔死 services.txt 不重写 checksum external edit"
verify: "还原 .frw 备份后 restart_workcell --relaunch 600s 内 RELAUNCH-OK；重放同一处外改后同法楔死并弹同款校验和对话框（A/B 可重复）。"
provenance:
  issue: "#5563"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

ROBOGUIDE 工位文件 .frw 被外部编辑（如改 XML UserFrames 坐标）后，该工位每次引导必楔死：RGCore 存活但冻在 frmSplash、CPU≈0、Responding=True（假活）、Robot_1/services.txt 不重写、logfile.txt 无新写入；屏幕上弹「工作单元文件的校验与不正确。在ROBOGUIDE的外部编辑文件时发生。请尝试从工作单元目录内的备份重新加载。」模态框。误导性极强：若多个工位都被外改过，症状是「全机工位同死」，极易误判为环境层故障（服务链楔死/授权过期/终端安全软件劣化），实测服务重启、授权重放均无效。

## Root Cause

.frw 内嵌文件校验和，外部字节修改（即使只是加 XML 属性）破坏校验和；RGCore 加载时校验失败弹模态框，该框卡住加载线程走不完引导链（弹窗本身非致命，关掉后加载只走半步仍僵死）。A/B 单变量实锤：同一工位同一环境，.frw 原件引导全绿（RELAUNCH-OK），外改版必楔；唯一变量 = 外改。

## Fix

① 修复 = 把工位目录内的备份拷回（*.frw.pocbak / *.frw.save / 原始副本覆盖 .frw），引导立即恢复；② 外改 .frw 路线的前置是破解校验和算法（未破），或改走 ROBOGUIDE 内部通道（程序内设值 + RG 自保存，校验和由 RG 维护）。诊断要点：弹窗文本直接点名根因；对照实验「原件 vs 外改」单变量钉死；排查多实例同死时先确认对照工位没被同一种外改污染。

## Verification

还原 .frw 备份后 restart_workcell --relaunch 600s 内 RELAUNCH-OK；重放同一处外改后同法楔死并弹同款校验和对话框（A/B 可重复）。
