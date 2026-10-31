---
title: "dsh-xdpool 测试连接报 content.some is not a function 异常修复"
domain: "mcp"
tags:
  - "dsh"
  - "xdpool"
  - "content"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-3815"
summary_plain: "在 dsh 0.2.1-rc.2 上点击 dsh-xdpool 插件的「测试连接」时必失败，报 TypeError: content.some is not a function。"
trigger: "dsh-xdpool 测试连接报 content.some is not a function 异常修复. 在 dsh 0.2.1-rc.2 上点击 dsh-xdpool 插件的「测试连接」时必失败，报 TypeError: content.some is not a function。"
verify: "在 node_modules/dsh-xdpool/lib/index.js 中修改 messages[0].content 为 [{ type: 'text', text: PROBE_PROMPT }]，语法检查通过后执行 dev_reload_package('dsh-xdpool') 热重载即恢复正常。"
public_analogue: "Array.prototype.some"
provenance:
  issue: "#3815"
  source: "MCP intake (remote-mcp), lesson submission converted by the maintainer"
---

## Problem

在 dsh 0.2.1-rc.2 上点击 dsh-xdpool 插件的「测试连接」时必失败，报 TypeError: content.some is not a function。

## Root Cause

probeModelConnectivity 函数调 ctx.llm.stream 时把 messages[0].content 传成纯字符串 PROBE_PROMPT，而 dsh-llm 运行时的 normalize 期望消息块数组 [{type: 'text', text: ...}]。

## Fix

在 node_modules/dsh-xdpool/lib/index.js 中修改 messages[0].content 为 [{ type: 'text', text: PROBE_PROMPT }]，语法检查通过后执行 dev_reload_package('dsh-xdpool') 热重载即恢复正常。

## Verification

Not recorded by the submitter.
