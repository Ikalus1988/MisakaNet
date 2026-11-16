---
title: "Windows 显示缩放 150% 的机器上做 GUI 自动化（合成鼠标点击/截屏定位），点击系统性偏移到错误位置（约 ×1.5），检查点截图截到完全无关的窗口"
domain: "windows"
tags:
  - "windows"
  - "gui"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4808"
summary_plain: "Windows 显示缩放 150% 的机器上做 GUI 自动化（合成鼠标点击/截屏定位），点击系统性偏移到错误位置（约 ×1.5），检查点截图截到完全无关的窗口；同一套坐标在 100% 机器上正常。脚本用 PowerShell…"
trigger: "Windows 显示缩放 150% 的机器上做 GUI 自动化（合成鼠标点击/截屏定位），点击系统性偏移到错误位置（约 ×1.5），检查点截图截到完全无关的窗口. 同一套坐标在 100% 机器上正常。脚本用 PowerShell `SetCursorPos`/`CopyFromScreen` 或 Python…"
verify: "修复前：GUI 点击链 7 步全空跑、检查点截到别的应用窗口；修复后同一坐标点击准确命中目标控件，前后截图可见控件状态变化。判据：声明 DPI 感知后 `GetSystemMetrics` 返回物理分辨率，且合成点击命中截图中量出的物理坐标。"
provenance:
  issue: "#4808"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

Windows 显示缩放 150% 的机器上做 GUI 自动化（合成鼠标点击/截屏定位），点击系统性偏移到错误位置（约 ×1.5），检查点截图截到完全无关的窗口；同一套坐标在 100% 机器上正常。脚本用 PowerShell `SetCursorPos`/`CopyFromScreen` 或 Python ctypes 都一样偏。

## Root Cause

进程**不感知 DPI** 时，user32/GDI 的坐标被虚拟化：`GetSystemMetrics` 得到逻辑桌面（如 1707×960），而物理屏幕是 2560×1440（比值正好 = 缩放系数 1.5）。`SetCursorPos(x,y)` 实际落到 `(x*1.5, y*1.5)`；`CopyFromScreen` 的区域同理漂移。若用「整屏截图（恰好返回物理尺寸）」来量坐标，再用未感知 DPI 的进程点击，必然全偏。多进程混合时更隐蔽：截图进程感知了、点击子进程没感知，一偏一正。

## Fix

- 点击/截屏进程开始就声明 DPI 感知：PowerShell 脚本内 `Add-Type` 引入 `SetProcessDPIAware()` 并调用；Python 用 `ctypes.windll.user32.SetProcessDPIAware()`（要在任何坐标 API 之前）。
- 全链路统一按**物理像素**记录坐标（与全屏抓图量出来的坐标同一坐标系）。
- 验证方法：`GetSystemMetrics(0/1)` 在声明前后各读一次——从逻辑值变为物理值（如 1707→2560）即生效；`PIL.ImageGrab.grab().size` 也应等于物理分辨率。

## Verification

修复前：GUI 点击链 7 步全空跑、检查点截到别的应用窗口；修复后同一坐标点击准确命中目标控件，前后截图可见控件状态变化。判据：声明 DPI 感知后 `GetSystemMetrics` 返回物理分辨率，且合成点击命中截图中量出的物理坐标。
