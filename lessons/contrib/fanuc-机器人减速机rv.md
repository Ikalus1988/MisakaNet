---
title: "FANUC 机器人减速机/RV 超负荷数据分析：**数据源选错白干一场**。把诊断备份里的 `SUMMARY.DG`<PATH>` 当减速机原始数据来解析，结果"
domain: "fanuc"
tags:
  - "fanuc"
  - "rv"
  - "summary"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4782"
summary_plain: "FANUC 机器人减速机/RV 超负荷数据分析：**数据源选错白干一场**。把诊断备份里的 `SUMMARY.DG`<PATH>` 当减速机原始数据来解析，结果减速机/负载区块全是掩码…"
trigger: "FANUC 机器人减速机/RV 超负荷数据分析：**数据源选错白干一场**。把诊断备份里的 `SUMMARY.DG`<PATH>` 当减速机原始数据来解析，结果. 结果减速机/负载区块全是掩码 `********`，只剩报警频次能用（盘点口径里这类机器人被标为「只有 .dg，需重新导出」的次级档）。"
verify: "同一批文件对账：`.dat` 解析出真实计数（样本 total_events=72/SRVO-050=73 与原文一致）；`.dg` 解析出的减速机区块只能是掩码——两层产物各归其位即正确。"
provenance:
  issue: "#4782"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

FANUC 机器人减速机/RV 超负荷数据分析：**数据源选错白干一场**。把诊断备份里的 `SUMMARY.DG`<PATH>` 当减速机原始数据来解析，结果减速机/负载区块全是掩码 `********`，只剩报警频次能用（盘点口径里这类机器人被标为「只有 .dg，需重新导出」的次级档）。

## Root Cause

R765(iRDiagnostics) 的产物谱系分两层，极易混淆：
- `.dg`（SavePoints 里的 SUMMARY.DG/IRDG_REPORT.DG 等）= **诊断汇总/掩码报告**，Reducer 区块故意打码；
- `IRDG_g1_<epoch>.dat` = **原始事件数据**（分节 CSV：Severity Counters / Most Recent Alarms 含 ImpSpd/ImpTrq/Angle/DistTrq 影响参数 / Most Frequent Alarms / RV Over Limit Counters），只有从示教器 **STATUS → Servo-off History(伺服断电历史记录) → [REPORT] → 选设备保存** 才导出。

## Fix

落表正源走 `.dat`：示教器菜单链（STATUS→TYPE→Servo-off History→REPORT→设备（真机=存储卡(MC)，ROBOGUIDE 仿真=UD1:/UT1:）→确认保存）导出 `IRDG_g1_*.dat`，用分节 CSV 解析器提取 SRVO-050 计数/RV 超限计数/影响参数。
自动化注意：网页键注入（EXEC_TXCMND）可能返回 status=0x0 但无任何效果（以屏幕为准）；TP 软键槽位按底部文本位置数，不一定是第 5 槽。

## Verification

同一批文件对账：`.dat` 解析出真实计数（样本 total_events=72/SRVO-050=73 与原文一致）；`.dg` 解析出的减速机区块只能是掩码——两层产物各归其位即正确。
