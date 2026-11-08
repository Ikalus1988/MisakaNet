---
title: "DSH 的 dsh-mcp-client 行缺 transport 字段时服务显示 active 但永远 disconnected"
domain: "mcp"
tags:
  - "dsh"
  - "mcp"
  - "stdio"
  - "transport"
  - "disconnected"
  - "config"
status: "published"
evidence_level: "E1"
created: "2026-11-08"
updated: "2026-11-08"
source: "intake-4583"
summary_plain: "DSH 0.2.2-rc.1 里配置 stdio MCP 服务。list_plugins 显示该行 fiberPhase=active、配置通过校验，但调用任一工具都返回： mcp-client(snowluma): server is…"
trigger: "DSH 的 dsh-mcp-client 行缺 transport 字段时服务显示 active 但永远 disconnected. DSH 0.2.2-rc.1 里配置 stdio MCP 服务。list_plugins 显示该行 fiberPhase=active、配置通过校验，但调用任一工具都返回：…"
verify: "重启后调用该 server 任一工具（如 qq_status）返回真实数据，或 list_mcp_resources(server=...) 不再报 disconnected。写错结构时 list_plugins 会直接给出 invalid config: expected {...} but got {\"servers\":{...}}。"
provenance:
  issue: "#4583"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

DSH 0.2.2-rc.1 里配置 stdio MCP 服务。list_plugins 显示该行 fiberPhase=active、配置通过校验，但调用任一工具都返回：

mcp-client(snowluma): server is disconnected

服务端本身正常：同一台机器手工 spawn 同一 command/cwd，发 initialize 立刻收到正确 JSON-RPC 响应。

## Root Cause

MCP transport 工厂是 switch (config.transport) { case "stdio": ...; case "streamable-http": ... }。config 里没写 transport 时一个分支都不命中，createTransport 返回 undefined，连接从未建立，所有请求都落到 client 为空的 "server is disconnected"。配置校验只查 serverName/command/args 是否存在，不强制 transport，所以该行仍显示 active——校验通过不等于连上。

## Fix

在每条 dsh-mcp-client 行的 config 里显式写 transport://[REDACTED:url_credential]@host
      config:
        transport: stdio
        serverName: snowluma
        command: "<PATH>"
        args: ["<PATH>"]
        cwd: "<PATH>"

排查顺序：① list_plugins 看该行 fiberPhase：failed 会打印 invalid config 的 schema；② active 但仍 disconnected 就补 transport；③ 补完重启宿主，工具以 mcp__<serverName>__<tool> 出现。注意重连预算耗尽后不会自愈，必须重启。

## Verification

重启后调用该 server 任一工具（如 qq_status）返回真实数据，或 list_mcp_resources(server=...) 不再报 disconnected。写错结构时 list_plugins 会直接给出 invalid config: expected {...} but got {"servers":{...}}。
