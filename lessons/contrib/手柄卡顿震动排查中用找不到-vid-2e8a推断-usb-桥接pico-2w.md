---
title: "手柄卡顿/震动排查中，用「找不到 VID_2E8A」推断 USB 桥接（Pico 2W 转发器）未接入，结论错误。 Root Cause 桥接固件伪装成真手柄上"
domain: "dsh"
tags:
  - "vid"
  - "e8a"
  - "usb"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4565"
summary_plain: "手柄卡顿/震动排查中，用「找不到 VID_2E8A」推断 USB 桥接（Pico 2W 转发器）未接入，结论错误。"
trigger: "手柄卡顿/震动排查中，用「找不到 VID_2E8A」推断 USB 桥接（Pico 2W 转发器）未接入，结论错误。 Root Cause 桥接固件伪装成真手柄上. 手柄卡顿/震动排查中，用「找不到 VID_2E8A」推断 USB 桥接（Pico 2W 转发器）未接入，结论错误。"
verify: "移除桥接后卡顿消失、装回复现；基于 VID 缺席与序列号相似的两轮判断均被推翻。"
provenance:
  issue: "#4565"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

手柄卡顿/震动排查中，用「找不到 VID_2E8A」推断 USB 桥接（Pico 2W 转发器）未接入，结论错误。

## Root Cause

桥接固件伪装成真手柄上报 `VID_054C&PID_0CE6`，设备树只显示一个 DualSense，没有 VID_2E8A 条目。用 USB 序列号与芯片 ID 相似判定伪造也不成立（不同命名空间）。

## Fix

改用受控对照：记录故障 → 移除桥接改直连 → 同场景复测 → 仅当"移除后消失、装回复现"才判桥接为根因。

## Verification

移除桥接后卡顿消失、装回复现；基于 VID 缺席与序列号相似的两轮判断均被推翻。
