---
title: "宿主启动时 dsh-mcp-client 连不上远端 MCP(这里是 misakanet.org;内陆到 Cloudflare 的链路会出现整段几十秒 0 字节"
domain: "windows"
tags:
  - "reconnect"
  - "dsh"
  - "mcp"
status: "published"
evidence_level: "E1"
created: "2026-11-22"
updated: "2026-11-22"
source: "intake-5572"
summary_plain: "宿主启动时 dsh-mcp-client 连不上远端 MCP(这里是 misakanet.org;内陆到 Cloudflare 的链路会出现整段几十秒 0 字节的死区),默认 10 次重试(≈151 秒)后永久放弃、注销全部…"
trigger: "auto-review: the pending native tool schema is missing or ambiguous | mcp-client: server is disconnected | giving up after failed reconnect attempts"
verify: "把该行 reconnect.maxAttempts 设为 100000 并重启宿主:链路坏窗口里工具未注册时,netstat 到 misakanet.org:443 仍在持续新建连接(超过 5 分钟),链路恢复后 misakanet_search 能返回结果 → 通过;151 秒后连接彻底停止 → 未通过。 **Matched lesson (not helpful):**…"
provenance:
  issue: "#5572"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

宿主启动时 dsh-mcp-client 连不上远端 MCP(这里是 misakanet.org;内陆到 Cloudflare 的链路会出现整段几十秒 0 字节的死区),默认 10 次重试(≈151 秒)后永久放弃、注销全部 mcp__misakanet__* 工具,之后网络恢复也不自愈。

更把人带偏的是表面症状:调用工具报 `Error: Auto review of tool "mcp__misakanet__misakanet_search" failed; its body was not executed: auto-review: the pending native tool schema is missing or ambiguous`,看着像 auto-review 插件的 bug。实际原因是该工具在宿主注册表里根本不存在(INSPECT host Tool/listTools:misakanet 命中 0 次,正常注册的 wincu 命中 26 次),auto-review 只是拿调用名去请求头的工具表里查 schema,查不到就拒绝执行——每次调用都在跑之前被拒。会话里工具面还挂着,所以看着"能用"。

## Root Cause

`reconnect` 默认 {enabled:true, initialDelayMs:500, maxDelayMs:30000, maxAttempts:10}。启动窗口里抖几下就把预算烧光,进入 failed{reason:'gave-up'} 并注销工具、不再重试;插件自带的 cordis.patch.yml 没有覆盖这几个默认值。旧策略下这个重试循环在约 151 秒后停止。

## Fix

在 profile 的 cordis.patch.yml 末尾按 id 覆盖该行(config 要写全,替换语义会丢字段):

- id: misakanet-mcp
  name: 'misakanet'
  config: {transport: streamable-http, serverName: misakanet, url: 'https://misakanet.org/mcp', headers: {Origin: 'https://misakanet.org'}, toolCallTimeoutMs: 120000, startupTimeoutMs: 120000, failOnStartupError: false, reconnect: {enabled: true, initialDelayMs: 1000, maxDelayMs: 60000, maxAttempts: 100000}}

重启宿主后实测:客户端连续重试约 11 分钟,自己连上并注册了全部 8 个工具,没再放弃。已经放弃的行也可以先禁用→启用该行强制重连。

另:auto-review 把"工具不存在"报成"schema 缺失或歧义",把排查方向带偏了,DSH 侧值得区分这两种情况。

## Verification

把该行 reconnect.maxAttempts 设为 100000 并重启宿主:链路坏窗口里工具未注册时,netstat 到 misakanet.org:443 仍在持续新建连接(超过 5 分钟),链路恢复后 misakanet_search 能返回结果 → 通过;151 秒后连接彻底停止 → 未通过。

**Matched lesson (not helpful):** dsh-mcp-row-disconnected-reconnect-budget-exhausted
