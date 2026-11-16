---
title: "症状：Node fetch 到某 Cloudflare Workers 端点报 `TypeError: fetch failed`，curl 报 `Connec"
domain: "mcp"
tags:
  - "curl"
  - "node"
  - "fetch"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4879"
summary_plain: "症状：Node fetch 到某 Cloudflare Workers 端点报 `TypeError: fetch failed`，curl 报 `Connection timed out`/`Recv failure…"
trigger: "症状：Node fetch 到某 Cloudflare Workers 端点报 `TypeError: fetch failed`，curl 报 `Connec. Connection timed out`/`Recv failure: Connection was…"
verify: "钉住好 IP 后同一报文立即恢复：无鉴权头 → HTTP 401（闸门正常），带正确头 → HTTP 200 {\"ok\":true}；真客户端全链投递 2 条事件各回 200、本地发送队列清空。坏 IP 侧仍可稳定复现 RST/超时。 钉 IP 后 401/200 闸门行为正常、客户端 2 条事件 200 投递成功、队列清空；坏 IP 仍稳定复现失败。"
provenance:
  issue: "#4879"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

症状：Node fetch 到某 Cloudflare Workers 端点报 `TypeError: fetch failed`，curl 报 `Connection timed out`/`Recv failure: Connection was reset`，误判为服务端宕机；但同网络下生产端点（CF 自定义域）HTTP 200 正常、api.github.com 200 正常。间歇性：同一 URL 有时超时有时重置。

## Root Cause

裸 `*.workers.dev` 域名解析出两个 CF anycast IP（如 172.67.162.111 与 104.21.66.170），网络侧只掐了其中一个（SYN 丢弃或 TLS 前 RST），另一个完全正常。DNS 轮询/多地址尝试随机命中坏 IP，于是「同一域名时通时断」，且错误发生在 TCP 层（connect 超时/recv reset），看起来像服务端故障。挂自定义域的 CF 服务不走这个封锁，所以对照组正常。

## Fix

逐 IP 定界而不是整域重试：`curl --resolve host:443:<ip>` 对解析出的每个 IP 单独探测，找出通的那颗钉住。客户端不支持钉 IP 时：①Node 侧自定义 lookup 回调钉 IP（注意 Node≥20 lookup 可能带 {all:true}，要 cb(null,[{address,family}]) 回数组，回 (addr,family) 会报 `ERR_INVALID_IP_ADDRESS: undefined`）；②或本地 HTTP 中继转发到钉住的 IP。根治：给端点挂自定义域（与生产同款）。

## Verification

钉住好 IP 后同一报文立即恢复：无鉴权头 → HTTP 401（闸门正常），带正确头 → HTTP 200 {"ok":true}；真客户端全链投递 2 条事件各回 200、本地发送队列清空。坏 IP 侧仍可稳定复现 RST/超时。

钉 IP 后 401/200 闸门行为正常、客户端 2 条事件 200 投递成功、队列清空；坏 IP 仍稳定复现失败。
