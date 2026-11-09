---
title: "高缩放多窗口下 GUI 自动化连环踩坑：坐标语义、截图裁剪、z-order、锁屏句柄失效"
domain: "windows"
tags:
  - "problem"
  - "windows"
  - "gui"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4601"
summary_plain: "Windows GUI 自动化在高缩放（如 2560×1440@150%）多窗口环境下连环踩坐标/捕获陷阱：①同一进程内 GetWindowRect 返回逻辑坐标而 SetCursorPos/GetCursorPos 语义随…"
trigger: "Problem Windows GUI 自动化在高缩放（如 2560×1440@150%）多窗口环境下连环踩坐标/捕获陷阱：①同一进程内 GetWindowRe. Windows GUI 自动化在高缩放（如 2560×1440@150%）多窗口环境下连环踩坐标/捕获陷阱：①同一进程内 GetWindowRect…"
verify: "可复现对照：同一批点击在坐标换算修正前全部假阴性，按「GetCursorPos 回读一致 + 窗口矩形偏移实测 + TOPMOST」修正后一次命中；锁屏时段全屏捕获报「句柄无效」而 PrintWindow 同期正常出图。 修正前后同点击假阴性→一次命中的对照；锁屏下两种捕获 API 行为对照"
provenance:
  issue: "#4601"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

Windows GUI 自动化在高缩放（如 2560×1440@150%）多窗口环境下连环踩坐标/捕获陷阱：①同一进程内 GetWindowRect 返回逻辑坐标而 SetCursorPos/GetCursorPos 语义随 DPI-aware 状态变化，点击落点偏移 1.5 倍；②CopyFromScreen 在 DPI-unaware 进程捕获的是逻辑分辨率裁剪（画面右/下被截断，视觉测量随之偏）；③遮挡关系未处理时合成点击落到上层窗口（看着点在目标上实际被别的窗口吃掉）；④锁屏瞬间 CopyFromScreen 抛「句柄无效」、GDI 捕获全灭，而 PrintWindow（渲染窗口自身）不受锁屏影响；⑤VB6 应用模态对话框与发起点击的脚本形成自死锁：SendMessage(按钮) 阻塞至模态框关闭，而关闭它的代码排在同一脚本后面。

## Root Cause

DPI 虚拟化按进程感知级别改变 USER32 坐标语义；截图 API 的坐标空间与窗口 API 不一致时，「按截图坐标点窗口」必偏移；窗口 z-order 和交互式桌面（锁屏安全桌面）决定注入输入的实际落点；SendMessage 对模态消息循环是同步阻塞语义。

## Fix

GetCursorPos 回读钉坐标系；PrintWindow 实测控件偏移；TOPMOST 防遮挡；模态框旁路处理；锁屏用 PrintWindow

## Verification

可复现对照：同一批点击在坐标换算修正前全部假阴性，按「GetCursorPos 回读一致 + 窗口矩形偏移实测 + TOPMOST」修正后一次命中；锁屏时段全屏捕获报「句柄无效」而 PrintWindow 同期正常出图。

修正前后同点击假阴性→一次命中的对照；锁屏下两种捕获 API 行为对照
