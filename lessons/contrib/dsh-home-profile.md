---
title: "DSH 插件安装时虚拟 HOME 环境变量导致 profile 安装路径漂移"
domain: "devops"
tags:
  - "dsh"
  - "home"
  - "profile"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-3814"
summary_plain: "在多账号沙箱/子账号或特定 Agent 环境中执行 dsh plugin --profile web add <pkg>，命令成功但在主宿主环境未生效。检查发现新插件被初始化到了子路径下的 ~/.dsh/profiles/web。"
trigger: "DSH 插件安装时虚拟 HOME 环境变量导致 profile 安装路径漂移. 在多账号沙箱/子账号或特定 Agent 环境中执行 dsh plugin --profile web add…"
verify: "在执行 dsh plugin 命令前显式前置指定宿主真实的 HOME 变量：HOME=<PATH> dsh plugin --profile web add <pkg>；或 cd 到宿主 profile 目录核对 package.json 后安装。"
provenance:
  issue: "#3814"
  source: "MCP intake (remote-mcp), lesson submission converted by the maintainer"
---

## Problem

在多账号沙箱/子账号或特定 Agent 环境中执行 dsh plugin --profile web add <pkg>，命令成功但在主宿主环境未生效。检查发现新插件被初始化到了子路径下的 ~/.dsh/profiles/web。

## Root Cause

dsh CLI 强依赖 process.env.HOME 解析 ~/.dsh 路径。当子进程 HOME 指向沙箱或隔离工作区时，dsh 会静默在虚拟 HOME 下初始化一套新的独立 profile，与宿主主进程脱钩。

## Fix

在执行 dsh plugin 命令前显式前置指定宿主真实的 HOME 变量：HOME=<PATH> dsh plugin --profile web add <pkg>；或 cd 到宿主 profile 目录核对 package.json 后安装。

## Verification

Not recorded by the submitter.
