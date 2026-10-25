---
title: "Reopening the workcell is itself a trigger: avoiding tpconn does not stop the PMON reconnect storm"
domain: "fanuc"
tags:
  - "roboguide"
  - "rgcore"
  - "pmon"
  - "reconnect-storm"
  - "watchdog"
  - "endpoint-security"
  - "virtual-controller"
  - "mitigation-boundary"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "重开工作单元本身就会自动触发 PMON 回环重连风暴，不需要任何示教器操作；所以「避开 tpconn」只是减小频率，止血不等于修复。"
trigger: "重开工作单元后 4 分钟内 OS -145 复发 / PMON Connected to TP 127.0.0.1:50005 ×15 / 避开 tpconn 仍崩溃 / 断电复位只止血"
verify: "复位后不做任何示教器操作、只重开工作单元：logfile 的 Memory access violation / OS -145 计数增量 > 0 即复发；RGCore Responding=True 与 CPU 缓慢增长不能判健康。"
source: "intake-3305"
provenance:
  issue: "#3305"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# Reopening the workcell is itself a trigger: avoiding tpconn does not stop the PMON reconnect storm

## Problem

既有经验 `fanuc-rgcore-hang-endpoint-security-injection` 的根因判定是对的（用户态 DLP Detours 注入 + WFP 内核过滤 + EDR 驱动三层组合导致 `frsock.dll` 在 `connect()` 崩溃），按它定位一次命中。但它的**缓解建议不完整**，会让人误以为「避开操作就能用」。该经验 Fix 第四步第 1 条写：

> 避开触发条件——运行中不要执行 `tpconn`、不要切换本地↔远程示教器

实测这条不够：**重开工作单元本身就会自动触发同一连接风暴**，不需要任何人工操作。

## Root Cause

PMON→TP 的 `127.0.0.1:50005` 重连风暴在**工作单元加载 / 虚拟控制器 HOT START 时自动发生**，不是只有 `tpconn` 或 UI 切换才触发。触发面比原文描述更宽。

实测时间线（干净断电复位后立即重开，全程无任何示教器操作）：

```
09:42     杀 RGCore/frrobot/FRROBO~1，干净断电
09:43     重新打开工作单元
09:47:28  控制器 HOT START
09:47:56  tpmains ready
09:47     PMON Connected to TP 127.0.0.1:50005 ×15   ← 自动发生
09:47     proxy/telnet/ftp/httpd/opcua/sytimque 连环 abort ×8
09:47     OS -145 ×8
```

即复位 + 重开后 **4 分钟内复发**。断电复位只是止血，不是修复；仅靠「避开 tpconn」无法在此类机器上稳定使用。

## Solution

对既有经验的补充（不推翻其根因结论）：

1. **缓解措施降级**：「避开 tpconn / 不切换示教器」只能减少触发频率，**不能消除**。在未加白的三层防护工控站上，工作单元重开即可能复发。
2. **必须走根治**：给 FANUC 目录加注入排除白名单 + 杀软对 `127.0.0.1` 回环加例外。原文称「本例没有完成这一步的闭环验证」，现在可以明确：**没有白名单时，该机器不能用于任何 FANUC 仿真无人值守任务**。
3. **看门狗判据改写**：不要用 RGCore 进程存活判定健康。原文已提到「假活」，但实操中极易忽略——本例曾因此误报「复位后 59 分钟干净」，实际控制器 4 分钟就死了。看门狗必须盯 `<工作单元>/Robot_1/logfile.txt` 的签名增量，而不是进程表。

## Verification

判定复发（而非 UI 问题）：

- `logfile.txt` 中 `Memory access violation` / `Module 'x' aborting` / `OS  -145` 计数**增量 > 0**；
- `PMON Connected to TP 127.0.0.1:50005` 短时间出现 ≥3 次（重连风暴）；
- `SEC -004 FSAC SNPX deny connect 1.0.0.127` 出现。

判定「假活」（不要被骗）：

- RGCore `Responding=True`、CPU 缓慢增长、窗口标题正常，但 logfile 已有崩溃签名 → 控制器已死；
- 3 秒 CPU 采样 dCPU ≤ 0.1 且内存不动（既有经验的判据）同样适用于 `frrobot` / `FRROBO~1`。

判定缓解有效（加白后）：同一工作单元重开 + 主动 `tpconn 0`，logfile 中 `0x2745` / `0x2746` 消失，无 `Memory access violation`。

复测环境：ROBOGUIDE V9.40179.0.4 / FRVRC V9.40，三层防护含注入型 DLP + AMSI Provider EDR + WFP 过滤。该组合之外的机器上重开工作单元不会复现，不要据此判定环境正常；报料者未给出无防护对照机的复测结果，需复现确认。
