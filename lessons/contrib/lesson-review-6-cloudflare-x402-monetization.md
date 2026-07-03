---
title: "Cloudflare Monetization Gateway — x402 API 支付协议"
domain: "ops"
subdomain: "api"
tags: ["cloudflare", "x402", "api", "monetization", "payment", "mcp"]
source: "blog.cloudflare.com"
status: "published"
confidence: "0.8"
created: "2026-07-01"
verified_date: ""
domain_expert: ""
---


## Problem

Web 30 年来的经济模式是"内容换注意力"（广告/订阅/电商）。AI Agent 时代，Agent 不看广告、不订阅、不浏览——传统变现模式失效。

## Root Cause

AI Agent 通过 API 访问内容，绕过了人类注意力经济。需要新的变现协议让 Agent 能直接付费。

## Solution

### Cloudflare Monetization Gateway

通过 x402 开放协议，让 Cloudflare 客户对任何资产收费：网页、数据集、API、MCP 工具。

```
Agent → Cloudflare Edge → 验证支付 → 放行请求 → Origin
         ↓
    x402 协议（稳定币结算）
```

### x402 协议设计

```http
# Agent 请求资源
GET /api/data HTTP/1.1
Host: api.example.com

# 服务器返回 402 Payment Required
HTTP/1.1 402 Payment Required
X-Payment-Required: true
X-Price: 0.01
X-Currency: USDC

# Agent 发送支付证明
GET /api/data HTTP/1.1
Host: api.example.com
X-Payment: <signed-payment-proof>

# 服务器验证后放行
HTTP/1.1 200 OK
```

### 适用场景

| 场景 | 示例 |
|------|------|
| API 按调用收费 | 每次 API 调用 $0.001 |
| 数据集按访问收费 | 每次下载 $0.01 |
| MCP 工具按使用收费 | 每次工具调用 $0.005 |
| 网页按爬取收费 | 每次 Agent 爬取 $0.002 |

### 与 MCP 的关系

MCP 工具可以通过 x402 协议收费：

```json
{
  "name": "search_documents",
  "description": "Search enterprise documents",
  "inputSchema": { ... },
  "pricing": {
    "x402": {
      "amount": "0.005",
      "currency": "USDC"
    }
  }
}
```

## Verification

1. 在 Cloudflare 配置 Monetization Gateway
2. 对一个 API 端点设置 x402 支付策略
3. Agent 请求该端点 → 收到 402
4. Agent 发送支付证明 → 收到 200 + 数据

## Notes

- x402 是开放协议，25+ 行业领导者共建
- 支付在 Cloudflare Edge 验证，保护 Origin 不被高支付量冲垮
- 稳币结算，非加密货币投机
- Source: blog.cloudflare.com (2026-07-01)
