---
title: "pnpm store 位置不一致会让 DSH 插件「一键安装」静默失败（ERR_PNPM_UNEXPECTED_STORE）"
domain: "dsh"
tags:
  - "dsh"
  - "pnpm"
  - "store-dir"
  - "plugin-install"
  - "silent-failure"
status: "published"
evidence_level: "E1"
created: "2026-11-08"
updated: "2026-11-08"
source: "intake-4585"
summary_plain: "DSH 插件页里点「一键安装」，按钮毫无反应也没有报错，重试多次无效。插件本身在 npm 上存在且可访问。"
trigger: "pnpm store 位置不一致会让 DSH 插件「一键安装」静默失败（ERR_PNPM_UNEXPECTED_STORE）. DSH 插件页里点「一键安装」，按钮毫无反应也没有报错，重试多次无效。插件本身在 npm 上存在且可访问。"
verify: "改完 pnpm add <pkg> 无 ERR_PNPM_UNEXPECTED_STORE 并能装成功；GUI 里的一键安装也随之可用（它走同一条 pnpm 路径）。"
provenance:
  issue: "#4585"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

DSH 插件页里点「一键安装」，按钮毫无反应也没有报错，重试多次无效。插件本身在 npm 上存在且可访问。

在 profile 目录用命令行执行 pnpm add 才看到真因：

ERR_PNPM_UNEXPECTED_STORE Unexpected store location
The dependencies at "<profile>/node_modules" are currently linked from the store at "<PATH>".
pnpm now wants to use the store at "<PATH>" ...

## Root Cause

profile 的 node_modules 是由自定义 store（例如 <PATH> pnpm 的全局 store-dir 被清掉/丢失，于是 pnpm 回落到默认位置 <盘符>\.pnpm-store，与已链接的 store 不一致，pnpm 拒绝操作。GUI 的安装按钮吞掉了 pnpm 的 stderr，所以表现为「点了没反应」。清理用户目录（例如删掉 %LOCALAPPDATA%\pnpm）会连带删掉 pnpm 全局配置，是常见诱因。

## Fix

两步：
1. 让全局 store 与 profile 已链接的 store 一致：
     pnpm config set store-dir <profile node_modules 实际使用的目录> --global
   用 `pnpm store path` 或报错信息里的 "linked from the store at ..." 确认目标。
2. 再用同一 store 重装/增删：
     pnpm add <pkg> --config.store-dir=<同一个目录>

排查口诀：任何「装完没反应 / 静默失败」的插件安装，先在 profile 目录手工跑一次 pnpm add 看完整报错，多半是 store 或 registry 问题，而不是插件本身坏了。

## Verification

改完 pnpm add <pkg> 无 ERR_PNPM_UNEXPECTED_STORE 并能装成功；GUI 里的一键安装也随之可用（它走同一条 pnpm 路径）。
