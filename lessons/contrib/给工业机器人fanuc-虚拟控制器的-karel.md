---
title: "给工业机器人（FANUC 虚拟控制器）的 KAREL 运动程序下发「正好等于软限位」的关节目标（如 J4=-190.00，限位恰为 -190），"
domain: "fanuc"
tags:
  - "mctl-003"
  - "the"
  - "fanuc"
status: "published"
evidence_level: "E1"
created: "2026-11-27"
updated: "2026-11-27"
source: "intake-5874"
summary_plain: "给工业机器人（FANUC 虚拟控制器）的 KAREL 运动程序下发「正好等于软限位」的关节目标（如 J4=-190.00，限位恰为 -190），机器人到点后控制器进入错误态：后续所有运动指令报 `INTP-313 Motion…"
trigger: "INTP-313 MCTL-003 system is in error status over travel limit edge f32 rounding motion failed"
verify: "复现：对任意关节下发精确等于软限位的目标并执行，到点后下一条运动指令必报 INTP-313/MCTL-003。对照：目标改为限位内 0.5° 的值，运动链正常继续（本例 7/9 样本一次到点，贴限位的第 8 个之后全灭）。 commanding a target exactly at the soft limit reproduces INTP-313/MCTL-003 on the next…"
provenance:
  issue: "#5874"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

给工业机器人（FANUC 虚拟控制器）的 KAREL 运动程序下发「正好等于软限位」的关节目标（如 J4=-190.00，限位恰为 -190），机器人到点后控制器进入错误态：后续所有运动指令报 `INTP-313 Motion statement failed` + `MCTL-003 system is in error status`，重发/ABORT 无效，整个采样任务后半程报废。

## Root Cause

目标值在 REAL→JOINTPOS（f32）转换中发生舍入下溢：十进制 -190.00 的 f32 表示是 **-190.000003**，恰好越过 -190 的软限位 3 微度 → 控制器按 over-travel 处理并进入 MCTL-003 错误态。错误态一旦成立：KCL `RESET`（含 ABORT ALL 配合）清不掉、整机断电重启清不掉（SRAM 恢复的姿态仍在限位外，开机即重现错误）、临时放宽限位（系统变量 RW 可写、回读成功）也清不掉——FANUC 的 over-travel 恢复需要示教器侧 Limit Release + 点动退出，纯软件通道没有等效入口。

## Fix

1. **预防**：往软限位附近下发运动目标时留余量（≥0.05°，或按 f32 分辨率算：限位值 ± 2^-14 度级），永远不要把「精确等于限位」的十进制值当安全目标；边缘采样点取限位内 0.5°。
2. **中招后**：别在 RESET/重启/放宽限位上浪费轮次（三招实测全无效）——直接安排示教器 Limit Release + 点动退出（GUI/手动腿），或放弃该轴后续样本并在报告里如实记「错误态拦死」。

## Verification

复现：对任意关节下发精确等于软限位的目标并执行，到点后下一条运动指令必报 INTP-313/MCTL-003。对照：目标改为限位内 0.5° 的值，运动链正常继续（本例 7/9 样本一次到点，贴限位的第 8 个之后全灭）。

commanding a target exactly at the soft limit reproduces INTP-313/MCTL-003 on the next move; same target pulled 0.5° inside the limit keeps the motion chain alive
