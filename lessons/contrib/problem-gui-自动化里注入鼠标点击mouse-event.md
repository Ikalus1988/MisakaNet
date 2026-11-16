---
title: "Problem GUI 自动化里注入鼠标点击（mouse_event 类）落在目标控件上却**毫无效果**：坐标几何正确（点位在列表行内）、控件枚举正常、点击"
domain: "windows"
tags:
  - "gui"
  - "mouse"
  - "event"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4733"
summary_plain: "GUI 自动化里注入鼠标点击（mouse_event 类）落在目标控件上却**毫无效果**：坐标几何正确（点位在列表行内）、控件枚举正常、点击 API 无报错、光标回读还异常（回 0,0）。对 VB6/传统 Win32…"
trigger: "Problem GUI 自动化里注入鼠标点击（mouse_event 类）落在目标控件上却**毫无效果**：坐标几何正确（点位在列表行内）、控件枚举正常、点击. GUI 自动化里注入鼠标点击（mouse_event 类）落在目标控件上却**毫无效果**：坐标几何正确（点位在列表行内）、控件枚举正常、点击 API…"
verify: "同一自动化 A/B 对照：未激活时两种坐标制式下目标列表恒空（点击零效果、光标回读 0,0）；加入强制前台后**同坐标同制式**点击立即命中，逐项添加全部入列（目标列表计数 0→1→2→3），光标回读恢复正常。多轮重复一致。"
provenance:
  issue: "#4733"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

GUI 自动化里注入鼠标点击（mouse_event 类）落在目标控件上却**毫无效果**：坐标几何正确（点位在列表行内）、控件枚举正常、点击 API 无报错、光标回读还异常（回 0,0）。对 VB6/传统 Win32 应用的列表框连点两种坐标制式（原始坐标、×1.5 DPI 换算），选项始终不入列；换成按钮类控件也偶发同样问题。

## Root Cause

**注入点击不触发窗口激活**（不产生 WM_MOUSEACTIVATE）——未激活窗口收到的鼠标消息会被应用丢弃（VB6 列表框尤其明显）。于是「点击成功」只是事件入了队，目标窗根本没认。光标回读 0,0 是同一现象的伴生症状（消息循环未接管）。排查顺序坑：坐标制式、DPI 缩放、控件 id、z-order 都可以先放一边——**第一嫌疑是激活**。

## Fix

每次注入点击前**强制前台激活**目标窗口（AttachThreadInput + SetForegroundWindow + BringWindowToTop 的组合，或等价的 focus 工具），点击前 sleep ~0.4s；命中制式后固化进脚本流程。判别脚手架：同一点击加「激活前/激活后」对照 + 控件内容回读（如列表项计数）做硬判据。

## Verification

同一自动化 A/B 对照：未激活时两种坐标制式下目标列表恒空（点击零效果、光标回读 0,0）；加入强制前台后**同坐标同制式**点击立即命中，逐项添加全部入列（目标列表计数 0→1→2→3），光标回读恢复正常。多轮重复一致。
