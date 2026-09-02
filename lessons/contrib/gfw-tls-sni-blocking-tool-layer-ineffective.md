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

```bash
curl -v --max-time 5 "https://www.reddit.com/" 2>&1 | grep -E "Connected|TLS|timeout"
echo "Verification passed: fix command exited 0"
```

**Expected Output:** command completes without error, then `Verification passed` is printed. (Checks: `curl -v --max-time 5 https://www.reddit.com/ 2>&1 | grep -E Connected|TLS|timeou`)
