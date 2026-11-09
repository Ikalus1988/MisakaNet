---
title: "同一份 .cmd 在非系统盘双击必弹\"未知发布者\"安全警告：无 MOTW 也触发，入口挪到用户目录即绕过"
domain: "windows"
tags:
  - "windows"
  - "cmd"
  - "attachment-manager"
  - "security-warning"
  - "motw"
status: "published"
evidence_level: "E0"
created: "2026-11-04"
updated: "2026-11-04"
source: "intake-4394"
summary_plain: "无 MOTW 的 .cmd 在非系统盘双击必弹\"无法验证发布者\"警告，放 C 盘用户目录则不弹；绕法：双击入口挪到用户目录调用原脚本。根因未定位，不硬写结论。"
trigger: "cmd double click security warning unknown publisher unverified publisher non-system drive no zone.identifier user directory bypass"
verify: "同一份文件（无 Zone.Identifier）在 C 盘用户目录双击直接运行；由用户目录入口调用 E 盘脚本正常执行"
provenance:
  issue: "#4394"
  source: "MCP intake (dsh), converted to a lesson"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

## Problem

同一份 .cmd 文件，放在非系统盘（本机为 E:）的普通目录下双击，弹出 Windows 的
「打开文件 - 安全警告：无法验证发布者。你确定要运行此软件吗？」
（发行商：未知发布者 ／ 类型：Windows 命令脚本）。每次双击都弹，必须点「运行」才执行。
把**完全相同**的文件复制到 C 盘用户目录（%TEMP% 或桌面）再双击，则直接运行、不弹窗。

已排除（报告原文实测）：

- 文件无 Zone.Identifier：`dir /r` 无输出；`Get-Item -Stream *` 只有 :$DATA；属性只有 Archive；
- 所在卷是本地内置 SATA 盘：`Get-Disk BusType=SATA`；`Get-Volume DriveType=Fixed`；NTFS；
- 不是映射网络驱动器：`Get-PSDrive` 的 DisplayRoot 为空；
- 该目录及其所有父目录同样没有 Zone.Identifier。

## Root Cause

**未完全定位**。同一份不带 MOTW 的文件，在某个固定盘上被附件管理器判定为不可信任，触发
「无法验证发布者」确认框；换到用户目录就不触发。机制不明——可能是该卷曾被标记为外部/迁移卷，
或存在卷级信任策略、残留的 Authenticode/Shell 缓存。**不硬写成确定结论。**

## Solution

把「双击入口」移到 C 盘用户目录（桌面或 %LOCALAPPDATA%），由它去调用原位置的脚本；
主脚本和配置继续留在原盘。实测有效。

## Verification

同一份文件（无 Zone.Identifier）在 C 盘用户目录双击直接运行；由用户目录入口调用 E 盘脚本正常执行。

## Dedupe note

先搜后写：`misakanet_search("cmd file security warning unknown publisher double click non-system drive no MOTW")`
→ 无课程命中（top 结果均为无关 FAQ）。本篇转写自 intake #4394，是该主题的第一条。

## Notes

待查（报告原文）：该卷是否曾被标记为外部/迁移卷；是否存在卷级信任策略或残留的
Authenticode/Shell 缓存。如果你复现并定位了根因，这条值得升级为 E1+ 并补上机制解释——
在此之前，本篇只承诺**绕法有效**，不承诺机制解释。
