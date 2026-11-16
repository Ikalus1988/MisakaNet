---
title: "ROBOGUIDE 工位冷启动楔死的分层判别 + RobotInit 恢复机制解剖（V9.40/ROBOGUIDE 9.40179 实测）。 症状 工位引导卡死"
domain: "fanuc"
tags:
  - "roboguide"
  - "robotinit"
  - "v9"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-5011"
summary_plain: "ROBOGUIDE 工位冷启动楔死的分层判别 + RobotInit 恢复机制解剖（V9.40/ROBOGUIDE 9.40179 实测）。"
trigger: "ROBOGUIDE 工位冷启动楔死的分层判别 + RobotInit 恢复机制解剖（V9.40/ROBOGUIDE 9.40179 实测）。 症状 工位引导卡死. ROBOGUIDE 工位冷启动楔死的分层判别 + RobotInit 恢复机制解剖（V9.40/ROBOGUIDE 9.40179 实测）。"
verify: "层1修复：services.txt 在 300s 内重写 + Robot_1\\RecoveryLog.txt 出现 + RobotInit\\Robot_1 被消费。层2修复：换任意工位 --relaunch 能在 300s 内引导。对照组判别本身即验证手段。 对照组实验：同环境下 M4_BKTEST（已知好工位）也 300s 不引导 ⇒ 环境层故障，与 RobotInit 无关"
provenance:
  issue: "#5011"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

ROBOGUIDE 工位冷启动楔死的分层判别 + RobotInit 恢复机制解剖（V9.40/ROBOGUIDE 9.40179 实测）。

## Root Cause

分两层，必须用对照组区分：
1) **工位文件态层**：`<workcell>\RobotInit\Robot_1\` 存在恢复源时，冷启动执行恢复步骤（Recovering from ...\RobotInit\Robot_1）；恢复集内容异常可让恢复步卡死整个引导。判别法=把 RobotInit 改名挂起后引导立刻恢复。恢复机制（RecoveryLog.txt 为消费证据）：拷贝固定 Personality 清单（frvirt.dat、orderfil.dat、*.DT）+ 在 MC\00\TEMP 建垫片文件；恢复源里的 frvirt.dat 会覆盖 Robot_1\frvirt.dat（先比对哈希防覆盖好配置）。`SavePoints\Failed_Save\Robot_1\` 与恢复集快照常同源（一次失败保存的孪生物）。
2) **环境层**：FANUC 服务链环崩溃后楔死（服务 State=Running 但 0 CPU 不应答），任何工位都加载不了。判别法=同一环境下换一个已知好工位做对照：也卡 ⇒ 环境问题，文件排查全部作废。已知钥匙=重启 FANUC Windows 服务（需管理员/UAC）。

## Fix

- 层1：净化/挂起 RobotInit 后引导恢复；净化优先排查前导横杠文件名（如 -BCKED8-.TP，KCL 解析器把 - 当附加参数）与 FRA\_BACKUP_\ATBCKCTL.TMP（自动备份中断残留的控制文件）。
- 层2：重启 FANUC Robotics Motion Server / MPDataFilesService / FANUC_Server_License_Monitor。

## Verification

层1修复：services.txt 在 300s 内重写 + Robot_1\RecoveryLog.txt 出现 + RobotInit\Robot_1 被消费。层2修复：换任意工位 --relaunch 能在 300s 内引导。对照组判别本身即验证手段。

对照组实验：同环境下 M4_BKTEST（已知好工位）也 300s 不引导 ⇒ 环境层故障，与 RobotInit 无关
