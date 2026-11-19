---
title: "同一台机器上先后装了两套 Filee（旧 2.2.0 在 <PATH> 为 per-user 安装，新 2.5.0 在 <PATH> Files\\Filee 为"
domain: "windows"
tags:
  - "delete"
  - "engines"
  - "filee"
status: "published"
evidence_level: "E1"
created: "2026-11-19"
updated: "2026-11-19"
source: "intake-5157"
summary_plain: "同一台机器上先后装了两套 Filee（旧 2.2.0 在 <PATH> 为 per-user 安装，新 2.5.0 在 <PATH> Files\\Filee 为 all-users 安装）。为清理旧版运行 `<PATH>…"
trigger: "uninstall old version deleted shared AppData engines folder / HKCU Run value removed by old uninstaller / two versions of same app installed, uninstall removed"
verify: "卸载后检查三处：`Test-Path \"$env:LOCALAPPDATA\\<App>\\engines\"` 与关键 exe 是否存在、`(Get-ItemProperty HKCU:\\...\\Run).<App>` 是否仍指向新版路径、桌面/开始菜单快捷方式 TargetPath 是否为新版 exe；再启动新版并确认日志出现新版本号的 started 行且功能（如 PDF 转换）正常。"
provenance:
  issue: "#5157"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

同一台机器上先后装了两套 Filee（旧 2.2.0 在 <PATH> 为 per-user 安装，新 2.5.0 在 <PATH> Files\Filee 为 all-users 安装）。为清理旧版运行 `<PATH> /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /LOG=...`，退出码 0、日志写 `delete settings: False`，但实际连带破坏了三处属于新版的东西：

1. `%LOCALAPPDATA%\Filee\engines` 整个被删（pandoc 引擎，5 文件 224.5 MB）——新版转换 PDF 会失效；
2. `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` 的 `Filee` 值被删除，而该值此时指向的是新版的 `<PATH> Files\Filee\Filee.exe --background`，等于关掉新版开机自启；
3. 桌面和用户开始菜单的 Filee.lnk 被删（这两个快捷方式还指向旧路径）。

## Root Cause

旧版卸载器按"自己的数据目录/同名快捷方式/同名自启项"做清理，而不是只删 uninstall.json 清单里属于旧安装目录的条目：AppData\Local\<App> 是两版共享的固定路径（与版本无关），HKCU Run 只按值名 `Filee` 判断，快捷方式只按文件名判断——所以旧版卸载会顺手清掉新版正在用的资源。日志里的 `delete settings: False` 只覆盖 settings.json，不覆盖 engines 目录和注册表自启项，容易误以为无副作用。

## Fix

卸载前备份共享数据目录和 Run 值 → 卸载 → 用备份还原目录、按原值重建 Run 键 → 修正快捷方式指向新路径。
实测还原后 `engines` 5 文件 224.5 MB、pandoc.exe 在位，`Filee` Run 值恢复为 `"<PATH> Files\Filee\Filee.exe" --background`，新版重新启动日志 `App: Filee 2.5.0 started`。

## Verification

卸载后检查三处：`Test-Path "$env:LOCALAPPDATA\<App>\engines"` 与关键 exe 是否存在、`(Get-ItemProperty HKCU:\...\Run).<App>` 是否仍指向新版路径、桌面/开始菜单快捷方式 TargetPath 是否为新版 exe；再启动新版并确认日志出现新版本号的 started 行且功能（如 PDF 转换）正常。
