---
title: "Equalizer APO 已正确挂到目标音频端点、`config.txt` 语法与设备选择器都正常，但 APO 完全没生效：`audiodg` 进程的模块列表"
domain: "windows"
tags:
  - "equalizer"
  - "apo"
  - "config"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4564"
summary_plain: "Equalizer APO 已正确挂到目标音频端点、`config.txt` 语法与设备选择器都正常，但 APO 完全没生效：`audiodg` 进程的模块列表里找不到 EqualizerAPO / LoudMax。"
trigger: "Equalizer APO 已正确挂到目标音频端点、`config.txt` 语法与设备选择器都正常，但 APO 完全没生效：`audiodg` 进程的模块列表. Equalizer APO 已正确挂到目标音频端点、`config.txt` 语法与设备选择器都正常，但 APO 完全没生效：`audiodg`…"
verify: "未切换默认设备前：播放任意声音后 `audiodg` 模块列表无 EqualizerAPO（因为流没走该端点）。 切换后：`audiodg` 中出现 EqualizerAPO / LoudMax，音量增益可感知。"
provenance:
  issue: "#4564"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

Equalizer APO 已正确挂到目标音频端点、`config.txt` 语法与设备选择器都正常，但 APO 完全没生效：`audiodg` 进程的模块列表里找不到 EqualizerAPO / LoudMax。

## Root Cause

默认播放设备不是该端点。实测三个角色的默认端点：
```
eConsole        -> Realtek
eMultimedia     -> Realtek
eCommunications -> DualSense   （仅通讯角色指向手柄）
```
APO 只挂在 DualSense 端点上，而系统提示音、音乐、视频默认都走 Realtek，DualSense 端点**根本没有音频流经过**，音频引擎不会为它实例化 APO，所以 `audiodg` 里查不到。此时无论怎么改 `config.txt`、重装 APO、重启音频服务都不会有变化。

## Fix

1. 先查默认端点指向：读 `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Render\{endpoint}\Properties` 下的 `{9855c4cd-df8c-449c-a181-8191a0f4d1e1},0` 等角色键，或用 COM `IPolicyConfig` / `IMMDeviceEnumerator` 查询 eConsole / eMultimedia / eCommunications 三个角色各自指向哪个端点。
2. 确认目标端点是否至少占一个角色；没有就切换默认输出到目标端点。
3. 切换后再播放音频，重新抓 `audiodg` 的已加载模块。

## Verification

未切换默认设备前：播放任意声音后 `audiodg` 模块列表无 EqualizerAPO（因为流没走该端点）。
切换后：`audiodg` 中出现 EqualizerAPO / LoudMax，音量增益可感知。
