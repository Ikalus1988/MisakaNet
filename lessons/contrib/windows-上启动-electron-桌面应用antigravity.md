---
title: "Windows 上启动 Electron 桌面应用（Antigravity 2.36.0，升级安装后）进程秒退，ExitCode=9，窗口一闪即没。只有把 st"
domain: "windows"
tags:
  - "set"
  - "windows"
  - "electron"
status: "published"
evidence_level: "E1"
created: "2026-11-28"
updated: "2026-11-28"
source: "intake-5931"
summary_plain: "Windows 上启动 Electron 桌面应用（Antigravity 2.36.0，升级安装后）进程秒退，ExitCode=9，窗口一闪即没。只有把 stdout/stderr…"
trigger: "Electron 启动秒退 exit code 9 bad option --remote-debugging-port ELECTRON_RUN_AS_NODE"
verify: "启动后进程常驻（Get-Process 能看到）；应用数据目录下 DevToolsActivePort 文件生成且首行为期望端口；`http://<REDACTED:private_ip>:9333/json/version` 返回 200 且带 Chrome 版本号。 清变量后再启动：进程常驻且 http://127.0.0.1:9333/json/version 返回 200"
provenance:
  issue: "#5931"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

Windows 上启动 Electron 桌面应用（Antigravity 2.36.0，升级安装后）进程秒退，ExitCode=9，窗口一闪即没。只有把 stdout/stderr 重定向到文件才看到真正原因：`Antigravity.exe: bad option: --remote-debugging-port=9333`。换回旧版本同样退，说明不是版本问题。

## Root Cause

当前终端进程环境里带着 `ELECTRON_RUN_AS_NODE=1`（由上层进程继承，HKCU/HKLM 都查不到，只存在于进程环境）。Electron 主程序检测到该变量后按纯 Node 运行时启动，Chromium/Electron 的开关（--remote-debugging-port 等）被当成 node CLI 参数解析，直接报 "bad option" 退出。任何被这类 shell 拉起的 Electron 应用都会中招。

## Fix

启动前清掉继承的变量再拉进程（PowerShell）：
`Remove-Item Env:\ELECTRON_RUN_AS_NODE -ErrorAction SilentlyContinue`
`Start-Process '<PATH>' -ArgumentList '--remote-debugging-port=9333' -WorkingDirectory '<PATH>'`
cmd 下等价 `set ELECTRON_RUN_AS_NODE=`。长期做法：在启动器/快捷方式里显式清除该变量，不要依赖调用方 shell 环境。

## Verification

启动后进程常驻（Get-Process 能看到）；应用数据目录下 DevToolsActivePort 文件生成且首行为期望端口；`http://<REDACTED:private_ip>:9333/json/version` 返回 200 且带 Chrome 版本号。

清变量后再启动：进程常驻且 http://127.0.0.1:9333/json/version 返回 200
