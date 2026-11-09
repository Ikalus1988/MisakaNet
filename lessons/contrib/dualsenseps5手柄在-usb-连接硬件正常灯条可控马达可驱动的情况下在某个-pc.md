---
title: "DualSense（PS5）手柄在 USB 连接、硬件正常（灯条可控、马达可驱动）的情况下，在某个 PC 游戏里完全没有震动；其他游戏正常。 Root Caus"
domain: "windows"
tags:
  - "dualsense"
  - "ps5"
  - "usb"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4569"
summary_plain: "DualSense（PS5）手柄在 USB 连接、硬件正常（灯条可控、马达可驱动）的情况下，在某个 PC 游戏里完全没有震动；其他游戏正常。"
trigger: "DualSense（PS5）手柄在 USB 连接、硬件正常（灯条可控、马达可驱动）的情况下，在某个 PC 游戏里完全没有震动；其他游戏正常。 Root Caus. DualSense（PS5）手柄在 USB 连接、硬件正常（灯条可控、马达可驱动）的情况下，在某个 PC 游戏里完全没有震动；其他游戏正常。"
verify: "- 直连 HID 发送 USB 输出报告 0x02（48 字节，flags=FF F7，右马达 byte3、左马达 byte4，灯条 RGB byte44-46），灯条变色且马达可感知 → 证明硬件链路正常； - 关闭音频增强后回到游戏，震动恢复。"
provenance:
  issue: "#4569"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

DualSense（PS5）手柄在 USB 连接、硬件正常（灯条可控、马达可驱动）的情况下，在某个 PC 游戏里完全没有震动；其他游戏正常。

## Root Cause

Windows 给该手柄的**扬声器音频端点**开启了音频增强 DSP（注册表 `MMDevices\Audio\Render\{endpoint}\Properties` 中 `{1da5d803-d492-4edd-8c23-e0c0ffee7f0e},3` 位标志 = 51 / 0x33，即"扬声器填充"+"音量均衡"同时启用，且"禁用所有增强功能"未勾选）。游戏自带 Sony 官方 `libScePad.dll` 走手柄音频通道输出触觉流，音频引擎在增强 DSP 链路上把触觉数据流破坏掉，结果就是"能响不能震"。

## Fix

1. 打开 声音设置 → 该手柄的"扬声器"属性 → 增强（Enhancements）→ 勾选 **"禁用所有增强功能"**；
2. 或直接改注册表把 `...,3` 位标志清掉（改前备份该键值）；
3. 一并检查端点是否被误设成默认播放设备（见"默认设备不是该端点则 APO/触觉流不加载"那条）。

## Verification

- 直连 HID 发送 USB 输出报告 0x02（48 字节，flags=FF F7，右马达 byte3、左马达 byte4，灯条 RGB byte44-46），灯条变色且马达可感知 → 证明硬件链路正常；
- 关闭音频增强后回到游戏，震动恢复。
