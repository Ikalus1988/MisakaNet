---
title: "本地工作台的表单通道用进程级随机令牌保护：`const UI_[REDACTED:credential] 403——页面还带着重启前的旧令牌，而失败只回一"
domain: "dsh"
tags:
  - "const"
  - "ui"
  - "redacted"
status: "published"
evidence_level: "E1"
created: "2026-11-22"
updated: "2026-11-22"
source: "intake-5514"
summary_plain: "本地工作台的表单通道用进程级随机令牌保护：`const UI_[REDACTED:credential] 403——页面还带着重启前的旧令牌，而失败只回一行 JSON（嵌在面板里根本看不出是授权失败）。"
trigger: "UI token random per process restart breaks open pages 403 button does nothing"
verify: "连续重启两次，令牌前后一致；重启前打开的页面提交表单仍返回 303 且状态文件更新，不再 403。 两次重启后 token 相同；重启前打开的页面点卡片有 303 + 状态变化，无 403。"
provenance:
  issue: "#5514"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

本地工作台的表单通道用进程级随机令牌保护：`const UI_[REDACTED:credential] 403——页面还带着重启前的旧令牌，而失败只回一行 JSON（嵌在面板里根本看不出是授权失败）。

## Root Cause

进程启动时生成的密钥只在该进程生命周期内有效。每次重启都会让所有已打开页面作废，而失败模式（赤裸的 403）和"按钮坏了"无法区分。

## Fix

令牌持久化到小文件（如 state/ui-token.json）：首次启动生成并写入，之后每次启动读回；文件缺失或非法才重新生成。服务端校验不变。

## Verification

连续重启两次，令牌前后一致；重启前打开的页面提交表单仍返回 303 且状态文件更新，不再 403。

两次重启后 token 相同；重启前打开的页面点卡片有 303 + 状态变化，无 403。
