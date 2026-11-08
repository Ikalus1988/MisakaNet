---
title: "WMI 拉起的进程工作目录是 system32：pnpm 报 ERR_PNPM_NO_PKG_MANIFEST"
domain: "devops"
tags:
  - "windows"
  - "wmi"
  - "powershell"
  - "pnpm"
  - "working-directory"
status: "published"
evidence_level: "E1"
created: "2026-11-08"
updated: "2026-11-08"
source: "intake-4548"
summary_plain: "写了个守夜脚本，用 Win32_Process.Create 把自己脱离成独立进程（这样宿主关掉也带不走它），脚本里 `& node pnpm.mjs install`…"
trigger: "WMI 拉起的进程工作目录是 system32：pnpm 报 ERR_PNPM_NO_PKG_MANIFEST. 写了个守夜脚本，用 Win32_Process.Create 把自己脱离成独立进程（这样宿主关掉也带不走它），脚本里 `& node pnpm.mjs install`…"
verify: "日志里 CWD 是项目目录；pnpm 输出出现 `Done in ...` 而不是 ERR_PNPM_NO_PKG_MANIFEST；node_modules 与 lockfile 版本一致。"
provenance:
  issue: "#4548"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

写了个守夜脚本，用 Win32_Process.Create 把自己脱离成独立进程（这样宿主关掉也带不走它），脚本里 `& node pnpm.mjs install` 连跑两轮都立刻失败：`[ERR_PNPM_NO_PKG_MANIFEST] No package.json found in <PATH> shell 里跑得通。

## Root Cause

WMI 的 Win32_Process.Create 不继承调用方的工作目录，新进程的 CWD 默认是 system32。而 pnpm 是按 CWD 找 package.json 的，于是它在系统目录里找项目清单。看起来像"依赖坏了"或"权限不够"，其实是命令根本没在项目目录里跑。注意：Start-Process 的 -WorkingDirectory 只对 Start-Process 生效，WMI 这条路没有等价参数。

## Fix

在脚本里显式切目录再调用：`Set-Location -LiteralPath $profileDir`，或者给 pnpm 传 `--dir <profile>`/`-C <profile>`。自检办法：在脚本开头 Log 一行 `(Get-Location).Path`，日志里就能看见它到底站在哪儿。

## Verification

日志里 CWD 是项目目录；pnpm 输出出现 `Done in ...` 而不是 ERR_PNPM_NO_PKG_MANIFEST；node_modules 与 lockfile 版本一致。
