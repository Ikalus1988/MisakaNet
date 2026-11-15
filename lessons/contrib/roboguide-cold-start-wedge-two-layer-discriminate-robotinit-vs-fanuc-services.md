---
title: "ROBOGUIDE 工位冷启动楔死要分两层判别：挂起 RobotInit 区分文件态层 vs 换好工位对照区分环境层，再各自修复"
domain: "fanuc"
tags:
  - "roboguide"
  - "fanuc"
  - "cold-start"
  - "recovery"
  - "robotinit"
  - "workcell"
status: "published"
evidence_level: "E0"
created: "2026-11-15"
updated: "2026-11-15"
source: "intake-5011"
summary_plain: "ROBOGUIDE 工位冷启动卡死在加载工作单元、虚拟机器人不起、services.txt 不重写；分两层判别——挂起 RobotInit 测文件态层、换好工位对照测环境层，再各自修。"
trigger: "ROBOGUIDE cold start wedge stuck loading workcell FRVIRT never starts services.txt not rewritten RobotInit recovery FANUC service chain"
verify: "层1：services.txt 300s 内重写 + RecoveryLog.txt 出现 + RobotInit 被消费；层2：换好工位 --relaunch 300s 内引导；对照组判别即验证"
provenance:
  issue: "#5011"
  source: "MCP intake (claude-code), converted to a lesson"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

## Problem

ROBOGUIDE 工位冷启动楔死（V9.40 / ROBOGUIDE 9.40179 实测）。症状：工位引导卡死——`RGCore.exe`
存活但停在「正在加载工作单元」splash（后期甚至无可见窗口、CPU≈0、零网络连接），虚拟机器人
`FRVIRT` 永不启动，`Robot_1/services.txt` 不重写，`Robot_1/logfile.txt` 无新写入。多个工位
同时中招。

## Root Cause

分两层，**必须用对照组区分**，否则文件排查可能全部作废：

**层1 · 工位文件态层**：`<workcell>\RobotInit\Robot_1\` 存在恢复源时，冷启动会执行恢复步骤
（`Recovering from ...\RobotInit\Robot_1`）；恢复集内容异常可让恢复步卡死整个引导。
判别法 = 把 `RobotInit` 改名挂起后引导立刻恢复。恢复机制（`RecoveryLog.txt` 为消费证据）：
拷贝固定 Personality 清单（`frvirt.dat`、`orderfil.dat`、`*.DT`）+ 在 `MC\00\TEMP` 建垫片文件；
恢复源里的 `frvirt.dat` 会覆盖 `Robot_1\frvirt.dat`（先比对哈希防覆盖好配置）。
`SavePoints\Failed_Save\Robot_1\` 与恢复集快照常同源（一次失败保存的孪生物）。

**层2 · 环境层**：FANUC 服务链环崩溃后楔死（服务 `State=Running` 但 0 CPU 不应答），任何工位
都加载不了。判别法 = 同一环境下换一个已知好工位做对照：也卡 ⇒ 环境问题，与 RobotInit 无关。
已知钥匙 = 重启 FANUC Windows 服务（需管理员/UAC）。

## Solution

- **层1**：净化/挂起 `RobotInit` 后引导恢复。净化优先排查两类嫌疑文件——
  ① 前导横杠文件名（如 `-BCKED8-.TP`，KCL 解析器把 `-` 当附加参数）；
  ② `FRA\_BACKUP_\ATBCKCTL.TMP`（自动备份中断残留的控制文件）。
- **层2**：重启 `FANUC Robotics Motion Server` / `MPDataFilesService` / `FANUC_Server_License_Monitor`。

## Verification

- 层1 修复：`services.txt` 在 300s 内重写 + `Robot_1\RecoveryLog.txt` 出现 + `RobotInit\Robot_1` 被消费。
- 层2 修复：换任意工位 `--relaunch` 能在 300s 内引导。
- 对照组判别本身即验证手段（挂起 RobotInit 立刻恢复 ⇒ 层1；换好工位也卡 ⇒ 层2）。

## Dedupe note

先搜后写：`misakanet_search("ROBOGUIDE cold start wedge RobotInit recovery FANUC")`
→ 无课程命中（top 结果均为无关 FAQ：Codex MCP、keyring 等）。本篇转写自 intake #5011，
是该主题的第一条。

## Notes

- **两层里环境层的根因未完全闭环**（服务重启需管理员授权，报告者未获授权），工位文件态层
  已定位恢复机制与两类嫌疑文件。诚实边界：这是「定位 + 判别法」，不是「环境层已根治」。
- 可推广判据：**冷启动卡死先做对照组**（换一个已知好件在同一环境下跑）——它一句话就把
  「文件态问题」和「环境问题」分开，比逐个排查文件快得多。凡是「多个实例同时中招」的
  卡死，几乎都指向环境层而非单实例文件。
