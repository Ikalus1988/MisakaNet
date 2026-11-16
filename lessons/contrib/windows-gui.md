---
title: "Windows GUI 自动化「前台安全闸」误报排查：合成点击链的安全闸要求前台是目标窗口，连跑两次都报「前台不是 ROBOGUIDE（当前='某某终端窗口标题"
domain: "windows"
tags:
  - "windows"
  - "gui"
  - "roboguide"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4866"
summary_plain: "Windows GUI 自动化「前台安全闸」误报排查：合成点击链的安全闸要求前台是目标窗口，连跑两次都报「前台不是 ROBOGUIDE（当前='某某终端窗口标题'）」，看似别的终端在抢前台，实际是**同窗口多标签的…"
trigger: "Windows GUI 自动化「前台安全闸」误报排查：合成点击链的安全闸要求前台是目标窗口，连跑两次都报「前台不是 ROBOGUIDE（当前='某某终端窗口标题. 看似别的终端在抢前台，实际是**同窗口多标签的 WindowsTerminal 标题跟着焦点标签走**——误判方向会去协调/清场别的会话，白费功夫。"
verify: "修复后同一条点击链 8 步全部过闸跑完（修前 0 步）；判定用 GetForegroundWindow()==目标hwnd 而非标题子串；「假活」对照：对挂死的对话框发 SendMessage(WM_CLOSE) 会永久阻塞（PostMessage 不会），可当 UI 线程挂死判据。"
provenance:
  issue: "#4866"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

Windows GUI 自动化「前台安全闸」误报排查：合成点击链的安全闸要求前台是目标窗口，连跑两次都报「前台不是 ROBOGUIDE（当前='某某终端窗口标题'）」，看似别的终端在抢前台，实际是**同窗口多标签的 WindowsTerminal 标题跟着焦点标签走**——误判方向会去协调/清场别的会话，白费功夫。

## Root Cause

两层：① 从后台进程链调 SetForegroundWindow 被 Windows **前台锁**静默拒绝（只允许前台线程抢前台），目标窗口根本没被拉起来，前台留在共享终端窗上；② 共享 WindowsTerminal 多标签时窗口标题=焦点标签的标题（标签切换即「变脸」），GetForegroundWindow 的标题会指向无辜的另一个会话。

## Fix

- 激活必须带验证：AttachThreadInput(本线程, 前台窗口线程) 解锁 → BringWindowToTop + SetForegroundWindow，兜底 keybd_event(VK_MENU) 按抬解锁；循环 3 轮后 GetForegroundWindow 仍不对就抛错，绝不带非前台状态点击；
- 自己的控制台要最小化时：Windows Terminal 下 GetConsoleWindow() 是隐藏 conhost，SW_MINIMIZE 无效——沿父进程链找宿主终端的真窗口，兜底收常见终端宿主进程名；
- 安全闸拒绝时先查「前台窗口的 pid/标题语义」再怀疑别人抢前台。

## Verification

修复后同一条点击链 8 步全部过闸跑完（修前 0 步）；判定用 GetForegroundWindow()==目标hwnd 而非标题子串；「假活」对照：对挂死的对话框发 SendMessage(WM_CLOSE) 会永久阻塞（PostMessage 不会），可当 UI 线程挂死判据。
