---
title: "反向代理后面 remoteAddress 永远是 127.0.0.1：按 IP 限流实际变成了全局限流"
domain: "nodejs"
tags:
  - "nodejs"
  - "cloudflare-tunnel"
  - "reverse-proxy"
  - "rate-limit"
  - "remoteaddress"
  - "x-forwarded-for"
status: "published"
evidence_level: "E1"
created: "2026-10-31"
updated: "2026-10-31"
source: "intake-4153"
summary_plain: "限流上线后，别人打满 10 次，**所有人（包括我自己）** 都开始 429，正常用户被别人的流量连坐。"
trigger: "反向代理后面 remoteAddress 永远是 127.0.0.1：按 IP 限流实际变成了全局限流. 限流上线后，别人打满 10 次，**所有人（包括我自己）** 都开始 429，正常用户被别人的流量连坐。"
verify: "两个不同出口各打 10 次，只有被打满的那个被限；日志里 `clientIP` 不再是 127.0.0.1；伪造 `x-forwarded-for` 直接请求源站不影响（源站只信任 CF）。"
provenance:
  issue: "#4153"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

限流上线后，别人打满 10 次，**所有人（包括我自己）** 都开始 429，正常用户被别人的流量连坐。

## Root Cause

服务走 Cloudflare Tunnel，源站看到的每个请求都来自 `127.0.0.1`。`req.socket.remoteAddress` 拿到的是代理地址，于是「按 IP 限流」退化成一个全局计数器。

## Fix

```js
function clientIP(req) {
  return (req.headers['cf-connecting-ip'] ||          // CF 覆盖写入，客户端伪造不了
          (req.headers['x-forwarded-for'] || '').split(',')[0].trim() ||
          req.socket.remoteAddress || '').replace(/^::ffff:/, '');
}
```
通用规则：任何「按客户端」的逻辑（限流、白名单、审计日志、灰度）都要先确认有没有可信的转发头，以及谁可以写它。

## Verification

两个不同出口各打 10 次，只有被打满的那个被限；日志里 `clientIP` 不再是 127.0.0.1；伪造 `x-forwarded-for` 直接请求源站不影响（源站只信任 CF）。
