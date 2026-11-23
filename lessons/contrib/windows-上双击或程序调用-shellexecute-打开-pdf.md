---
title: "Windows 上双击或程序调用 ShellExecute 打开 .pdf 时静默失败/无反应，文件本身完好（Edge 可正常打开）。 根因 `HKCU\\Sof"
domain: "windows"
tags:
  - "assoc"
  - "windows"
  - "shellexecute"
status: "published"
evidence_level: "E1"
created: "2026-11-22"
updated: "2026-11-22"
source: "intake-4671"
summary_plain: "Windows 上双击或程序调用 ShellExecute 打开 .pdf 时静默失败/无反应，文件本身完好（Edge 可正常打开）。"
trigger: "Windows 上双击或程序调用 ShellExecute 打开 .pdf 时静默失败/无反应，文件本身完好（Edge 可正常打开）。 根因 `HKCU\\Sof. Windows 上双击或程序调用 ShellExecute 打开 .pdf 时静默失败/无反应，文件本身完好（Edge 可正常打开）。"
verify: "修复前 `Start-Process -FilePath x.pdf` 抛异常；修复后同一调用成功、`cmd /c start \"\" x.pdf` 退出码 0，Edge 正常渲染。 注意：`assoc .pdf` 仍可能报 \"File association not found\"（它只读 HKLM 侧），不代表没修好，以 ShellExecute 实测为准。 Start-Process 打开…"
provenance:
  issue: "#4671"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

Windows 上双击或程序调用 ShellExecute 打开 .pdf 时静默失败/无反应，文件本身完好（Edge 可正常打开）。

## Root Cause

`HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.pdf\UserChoice` 的 ProgId 指向 `SLBrowserPDF`（联想浏览器 `<PATH> Files (x86)\Lenovo\SLBrowser\SLBrowser.exe`），该关联解析失败，ShellExecuteEx 返回 ERROR_NO_ASSOCIATION(1155)。PowerShell 报错文案为「无法完全运行此命令，因为系统找不到所需的全部信息」，容易被误判成文件损坏或程序没装。

## Fix

1. 备份：`reg export "HKCU\...\FileExts\.pdf" bak.reg /y`
2. 删除 `UserChoice` 子键（Windows 不允许直接改它的 ProgId，Hash 校验会拦截）
3. 设用户级默认：`HKCU\Software\Classes\.pdf` 的 (default) = `MSEdgePDF`（或 `KWPS.PDF.9` 走 WPS）
4. `SHChangeNotify(0x08000000, 0, 0, 0)` 刷新外壳缓存，无需重启 explorer

## Verification

修复前 `Start-Process -FilePath x.pdf` 抛异常；修复后同一调用成功、`cmd /c start "" x.pdf` 退出码 0，Edge 正常渲染。

注意：`assoc .pdf` 仍可能报 "File association not found"（它只读 HKLM 侧），不代表没修好，以 ShellExecute 实测为准。

Start-Process 打开 PDF 由失败转为成功；cmd start 退出码 0；Edge 正常显示 PDF 内容。GUI 端文件卡片待用户复测。
