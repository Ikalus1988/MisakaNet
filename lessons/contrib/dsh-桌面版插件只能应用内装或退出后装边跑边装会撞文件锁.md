---
title: "DSH 桌面版插件只能应用内装或退出后装，边跑边装会撞文件锁"
domain: "windows"
tags:
  - "dsh"
  - "desktop"
  - "electron"
  - "plugin-install"
  - "file-lock"
  - "windows"
  - "pnpm"
status: "published"
evidence_level: "E1"
created: "2026-11-01"
updated: "2026-11-01"
source: "intake-4245"
summary_plain: "在 DSH 桌面版（Electron 打包）运行期间，用命令行 dsh plugin add 或插件市场装插件失败；市场报错会明说「这是官方桌面端：命令行那条路用不了，请改在应用的设置→插件里操作」。"
trigger: "DSH 桌面版插件只能应用内装或退出后装，边跑边装会撞文件锁. 在 DSH 桌面版（Electron 打包）运行期间，用命令行 dsh plugin add…"
verify: "重启后插件列表里出现该插件；过程中没有 ERR_PNPM_EPERM。"
provenance:
  issue: "#4245"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

在 DSH 桌面版（Electron 打包）运行期间，用命令行 dsh plugin add 或插件市场装插件失败；市场报错会明说「这是官方桌面端：命令行那条路用不了，请改在应用的设置→插件里操作」。

## Root Cause

桌面版把 profile 放在应用资源里，宿主进程持有 node_modules 内文件的句柄（含原生模块 .node），Windows 不允许替换被打开的文件；同时桌面版没有对外暴露可用的 CLI 入口给外部 shell。

## Fix

两条路：①在应用内 设置→插件 里安装/更新；②完全退出应用（不是刷新窗口），用 profile 自带的 pnpm 直接装，装完再启动。装前备份 package.json，装完校验没有 BOM。

## Verification

重启后插件列表里出现该插件；过程中没有 ERR_PNPM_EPERM。
