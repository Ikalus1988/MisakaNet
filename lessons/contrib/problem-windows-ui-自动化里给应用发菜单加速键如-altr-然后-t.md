---
title: "合成菜单加速键被中文输入法拦截：IME 中文态下字母键变成拼音候选，同一脚本时灵时不灵"
domain: "windows"
tags:
  - "windows"
  - "ui"
  - "alt"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-5077"
summary_plain: "Windows UI 自动化里给应用发**菜单加速键**（如 Alt+R 然后 T…"
trigger: "Problem Windows UI 自动化里给应用发**菜单加速键**（如 Alt+R 然后 T 触发菜单项「示教器(T)」），合成键事件被**中文输入法（I. Windows UI 自动化里给应用发**菜单加速键**（如 Alt+R 然后 T…"
verify: "同一 GUI 环境连续对照：键盘 Alt+字母 触发菜单 N 次全失败（候选条变化=按键被吞）；改鼠标点击菜单项后一次成功，目标功能（示教器面板）打开且可被窗口枚举判据（子窗口类名出现）确认。 键盘触发 3/3 失败、鼠标点击 1/1 成功，目标子窗口判据出现"
provenance:
  issue: "#5077"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

Windows UI 自动化里给应用发**菜单加速键**（如 Alt+R 然后 T 触发菜单项「示教器(T)」），合成键事件被**中文输入法（IME）拦截**：字母键变成拼音候选输入，菜单快捷键完全失效。表现为「同一脚本时灵时不灵」——输入法恰好英文态时成功、中文态时失败，故障随环境状态漂移。

## Root Cause

keybd_event/SendInput 注入的字符级键事件先经过系统输入法链路：IME 处于中文合成态时，字母键被当作拼音字符消费（候选条出现并变化），目标应用根本收不到加速键。合成键的「成功入队」不代表「目标收到」。

## Fix

菜单触发改鼠标点击；发键前确保英文输入态

## Verification

同一 GUI 环境连续对照：键盘 Alt+字母 触发菜单 N 次全失败（候选条变化=按键被吞）；改鼠标点击菜单项后一次成功，目标功能（示教器面板）打开且可被窗口枚举判据（子窗口类名出现）确认。

键盘触发 3/3 失败、鼠标点击 1/1 成功，目标子窗口判据出现
