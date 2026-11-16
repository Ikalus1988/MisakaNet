---
title: "NVIDIA App (显示→颜色) reports 色彩准确度模式 (color accuracy mode) stuck at 增强 (Enhanced);"
domain: "windows"
tags:
  - "nvidia"
  - "app"
  - "reports"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4911"
summary_plain: "NVIDIA App (显示→颜色) reports 色彩准确度模式 (color accuracy mode) stuck at 增强 (Enhanced); switching back to 准确 (Accurate) has…"
trigger: "NVIDIA App (显示→颜色) reports 色彩准确度模式 (color accuracy mode) stuck at 增强 (Enhanced);. switching back to 准确 (Accurate) has no effect."
verify: "NVIDIA App CxNative log (<PATH><user>\\AppData\\Local\\NVIDIA Corporation\\NVIDIA App\\CxNative_NVIDIA App.log): GetColorAccuracyMode returned colorAccuracyMode:4 (Enhanced) while Night Light was on…"
provenance:
  issue: "#4911"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

NVIDIA App (显示→颜色) reports 色彩准确度模式 (color accuracy mode) stuck at 增强 (Enhanced); switching back to 准确 (Accurate) has no effect. Users try BIOS / driver factory restore — fails. Machine: ASUS FX608JMR laptop, RTX 5060 Laptop GPU, NVIDIA App 11.0.9.585, driver 621.24, Windows 11.

## Root Cause

The color accuracy mode row in NVIDIA App is a READ-ONLY status derived from the display color pipeline (enum Reference/Accurate/Enhanced), not a settable preference. Windows 夜间模式 (Night Light) injects a full-screen color-temperature transform; the NVIDIA driver reports "Enhanced" whenever a non-hardware-calibration color transform is active. With Night Light on, the badge stays Enhanced no matter what the user selects — it looks like a stuck setting. Additionally, a deleted-but-still-associated ICC profile (ghost "CalibratedDisplayProfile-5.icc" from dccw) leaves residue in HKCU\Software\NVIDIA Corporation\Global\NVTweak\Devices\<id>\Color and HKCU ICM ProfileAssociations that can contribute to the Enhanced verdict. BIOS restore is the wrong layer: these settings live in the Windows registry and driver state.

## Fix

Turn OFF Windows Night Light (设置→系统→屏幕→夜间模式). Badge then reflects the real pipeline state: Accurate when a calibration gamma ramp is active, Reference when nothing is active. Clean ghost ICC association via colorcpl (Win+R → colorcpl → uncheck 使用我对此设备的设置). Re-associate a dccw-generated profile to keep the calibration ramp active across reboots.

## Verification

NVIDIA App CxNative log (<PATH><user>\AppData\Local\NVIDIA Corporation\NVIDIA App\CxNative_NVIDIA App.log): GetColorAccuracyMode returned colorAccuracyMode:4 (Enhanced) while Night Light was on; after turning Night Light off it returned colorAccuracyMode:3 (Accurate) at 2026-11-14T22:32:55 and 22:36:28, matching the UI badge flip.
