---
title: GFW TLS SNI 阻断：工具层全部无效，只有代理能解
domain: devops
tags:
- gfw
- tls-sni
- scraper
- proxy
- china-network
status: published
created: '2026-07-01'
language: zh
source: <user>
confidence: 1.0
domain_expert: <user>
verified_date: '2026-07-06'
subdomain: network
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
summary_plain: "从中国大陆抓取 Reddit/StackOverflow 等站点时，所有工具层方案（curl、Playwright、scrapling、Safari MCP、WebFetch、Agent-Reach Jina…"
trigger: "GFW TLS SNI 阻断：工具层全部无效，只有代理能解. 从中国大陆抓取 Reddit/StackOverflow 等站点时，所有工具层方案（curl、Playwright、scrapling、Safari…"
verify: "在无代理环境下 `curl --noproxy '*' --max-time 12 https://www.reddit.com/` 在 12 秒内超时（curl: (28)），而同一主机经代理返回 200 —— 阻塞在网络层，换工具无用。若直连能完成 TLS 握手，本课不适用。"
---

## Problem

从中国大陆抓取 Reddit/StackOverflow 等站点时，所有工具层方案（curl、Playwright、scrapling、Safari MCP、WebFetch、Agent-Reach Jina Reader）全部超时失败。Agent 误判为"工具配置问题"，反复尝试不同工具浪费大量时间。

## Root Cause

GFW TLS SNI 嗅探阻断：
- DNS 正常解析 → Fastly CDN IP
- TCP 三次握手成功
- TLS Client Hello 的 SNI 字段被识别（如 `reddit.com`）
- Server Hello 被丢弃，10s 超时

**所有工具底层走同一 TCP+TLS 链路**，工具层无法绕过网络层封锁。

## Solution

### 诊断命令

```bash
curl -v --max-time 5 "https://www.reddit.com/" 2>&1 | grep -E "Connected|TLS|timeout"
# 期望看到: Connected → TLS handshake Client hello → timeout
```

### 判断流程

```
收到论坛链接
  → 第1层：白名单检查（robot-forum.com / GitHub / Dev.to / 掘金 → 直接抓取）
  → 第2层：curl TLS 握手测试
  → 握手超时 → SNI 阻断，走代理
  → 非超时错误（403/404）→ anti-bot 或 URL 问题，不是 GFW
```

### 国内直连白名单

| 站点 | 抓取方式 |
|------|----------|
| robot-forum.com | Playwright (WoltLab) |
| GitHub | gh CLI / REST API |
| Dev.to | REST API |
| Juejin 掘金 | Playwright |

### 唯一解法

```bash
export HTTPS_PROXY=http://ip:port
curl -x http://ip:port https://www.reddit.com/...
```

## Verification

**The check must fail when the network is blocked** — that is the whole claim. The previous version of
this section did not: it ran `curl` **through** whatever proxy the machine has, so it printed
`Verification passed` on a machine where the direct path is blocked (measured 2026-11-14, this
machine: through the proxy the handshake completes; with `--noproxy '*'` it times out). A check that
passes in both states is a comment.

```bash
# 1) the discriminating run: no proxy, so only the raw TCP+TLS path is exercised
curl -sS -v --noproxy '*' --max-time 12 https://www.reddit.com/ -o /dev/null 2>&1 \
  | grep -E 'Trying|Connected to|Client hello|Server hello|timed out'

# 2) the control: the same host through the proxy still answers
curl -sS --max-time 12 -o /dev/null -w 'proxied: %{http_code}\n' https://www.reddit.com/
```

**Expected output on a blocked network** (measured 2026-11-14):

```
*   Trying 157.240.7.20:443...
*   Trying [2001::1]:443...
* Connection timed out after 12000 milliseconds
curl: (28) Connection timed out after 12000 milliseconds
proxied: 200
```

Reading it: DNS answers with `157.240.7.20` (a Facebook range) **and** `2001::1` — both are poisoning,
not Reddit — and the direct attempt never reaches `Server hello`. The control succeeding is what proves
the failure is in the network path rather than in the tool.

**If your machine shows `Server hello` on the direct run**, this lesson does not apply to you: the
network is not blocking it, and another cause is in play.
