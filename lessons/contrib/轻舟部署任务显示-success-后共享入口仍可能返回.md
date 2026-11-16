---
title: "轻舟部署任务显示 SUCCESS 后，共享入口仍可能返回 502，并且应用实例仍处于已停止状态。 Root Cause 部署任务成功只代表构建和部署配置已处理，"
domain: "mcp"
tags:
  - "app.js"
  - "success"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4981"
summary_plain: "轻舟部署任务显示 SUCCESS 后，共享入口仍可能返回 502，并且应用实例仍处于已停止状态。"
trigger: "轻舟部署任务显示 SUCCESS 后，共享入口仍可能返回 502，并且应用实例仍处于已停止状态。 Root Cause 部署任务成功只代表构建和部署配置已处理，. 轻舟部署任务显示 SUCCESS 后，共享入口仍可能返回 502，并且应用实例仍处于已停止状态。"
verify: "启动后管理页显示运行中，`/health` 返回 200，线上 `app.js` SHA-256 与本地构建一致；随后完成 Safari 实机验收和本地 23/23 回归。"
provenance:
  issue: "#4981"
  source: "MCP intake (codex), lesson submission converted by the maintainer"
---

## Problem

轻舟部署任务显示 SUCCESS 后，共享入口仍可能返回 502，并且应用实例仍处于已停止状态。

## Root Cause

部署任务成功只代表构建和部署配置已处理，不保证共享入口已经绑定到新的运行实例；如果应用在部署时处于停止状态，入口没有后端可用，健康检查也会一直等待。

## Fix

不要回滚或删除。先确认部署任务和目标版本，再从管理页启动应用；若共享入口仍绑定旧实例，使用受控 stop/start 重建入口绑定，必要时重新部署当前标准包。

## Verification

启动后管理页显示运行中，`/health` 返回 200，线上 `app.js` SHA-256 与本地构建一致；随后完成 Safari 实机验收和本地 23/23 回归。
