---
title: "GUI 截图验收批量出图中途机器自动锁屏：CopyFromScreen/PowerShell 全程无报错，10 张「验收截图」全部拍成锁屏壁纸，脚本报成功——假"
domain: "windows"
tags:
  - "gui"
  - "copyfromscreen"
  - "powershell"
status: "published"
evidence_level: "E1"
created: "2026-11-24"
updated: "2026-11-24"
source: "intake-5711"
summary_plain: "GUI 截图验收批量出图中途机器自动锁屏：CopyFromScreen/PowerShell 全程无报错，10 张「验收截图」全部拍成锁屏壁纸，脚本报成功——假出图混进证据链。"
trigger: "CopyFromScreen lock screen screenshot silent success LogonUI capture wallpaper"
verify: "锁定工作站后运行出图脚本：必须非零退出并打印 locked 拒绝；解锁后同一脚本正常出图。双路径各跑一次全过=PASS。"
provenance:
  issue: "#5711"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

GUI 截图验收批量出图中途机器自动锁屏：CopyFromScreen/PowerShell 全程无报错，10 张「验收截图」全部拍成锁屏壁纸，脚本报成功——假出图混进证据链。

## Root Cause

工作站锁定后 GDI CopyFromScreen 仍可执行且返回成功，抓到的是锁屏（Winlogon 桌面）像素；出图脚本按窗口矩形取图、不校验内容，锁定前后返回码与日志无差别，静默产出废片。

## Fix

出图脚本加锁屏哨兵：检测 LogonUI 进程在场（工作站锁定/登录界面标志）即拒绝截图、报错退出；批量出图脚本把单张失败视为致命停批，宁可缺证不留假证；已生成的可疑截图按体积/内容抽查后再入证据链。

## Verification

锁定工作站后运行出图脚本：必须非零退出并打印 locked 拒绝；解锁后同一脚本正常出图。双路径各跑一次全过=PASS。
