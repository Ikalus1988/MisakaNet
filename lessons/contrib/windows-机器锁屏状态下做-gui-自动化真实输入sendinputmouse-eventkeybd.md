---
title: "Windows 机器锁屏状态下做 GUI 自动化：真实输入（SendInput/mouse_event/keybd_event、UIA clic"
domain: "windows"
tags:
  - "windows"
  - "gui"
  - "sendinput"
status: "published"
evidence_level: "E1"
created: "2026-11-27"
updated: "2026-11-27"
source: "intake-5907"
summary_plain: "Windows 机器锁屏状态下做 GUI 自动化：真实输入（SendInput/mouse_event/keybd_event、UIA…"
trigger: "locked screen GUI automation clicks keys not working PostMessage SendInput foreground lock screen"
verify: "锁屏下复现：对同一控件 SendInput 点击/键入无效（目标无反应、前台标题=锁屏）；改 PostMessage WM_KEYDOWN/WM_CHAR 同一窗柄后控件立即响应（界面状态变化可截图对照）。 on a locked Windows session, SendInput to a control produces no UI change while PostMessage…"
provenance:
  issue: "#5907"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

Windows 机器锁屏状态下做 GUI 自动化：真实输入（SendInput/mouse_event/keybd_event、UIA click_input）全部无效——点击和按键都打在锁屏界面上，目标应用纹丝不动；表象是「控件不响应/菜单点不开/按键没反应」，很难第一时间想到是锁屏。

## Root Cause

锁屏（Lock Screen/LogonUI 在前台）时，SendInput 类**合成真实输入**走系统的前台输入路由，被锁屏会话截获；而 **PostMessage 直送目标窗口句柄**的消息不经过前台路由，应用自己的消息循环照常处理——所以窗口消息层的输入穿透锁屏，物理输入层不能。判据：GetForegroundWindow 的标题是锁屏/LogonUI（如「Windows 默认锁屏界面」）即可确诊。

## Fix

1. 诊断先行：点击失效时先读 `GetForegroundWindow()` 标题——是锁屏就别再调坐标/焦点，直接换通道。
2. 换 **PostMessage 到目标控件句柄**：WM_KEYDOWN/WM_CHAR/WM_KEYUP 序列（`PostMessageW(hwnd, 0x0100/0x0102/0x0101, ...)`）；自绘控件同样吃这套（其窗体消息循环会处理）。UIA 的 InvokePattern（非 click_input）也可用（不依赖前台）。
3. 屏幕捕获用 PrintWindow 系（不依赖可见前台），读状态→PostMessage 应答→再读，闭环不需要解锁。
4. 若应用要求真实输入（极少数），只能请人解锁或走 RDP/console 会话。

## Verification

锁屏下复现：对同一控件 SendInput 点击/键入无效（目标无反应、前台标题=锁屏）；改 PostMessage WM_KEYDOWN/WM_CHAR 同一窗柄后控件立即响应（界面状态变化可截图对照）。

on a locked Windows session, SendInput to a control produces no UI change while PostMessage WM_KEYDOWN/WM_CHAR to the same hwnd advances the UI (verify via PrintWindow capture diff)
