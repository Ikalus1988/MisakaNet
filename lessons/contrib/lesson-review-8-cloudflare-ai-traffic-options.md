---
title: "Cloudflare AI Traffic Options — Content Monetization for the Agentic Internet"
domain: "ops"
subdomain: "api"
tags: ["cloudflare", "ai", "monetization", "crawling", "pay-per-crawl", "content"]
source: "blog.cloudflare.com"
status: "published"
confidence: "0.85"
created: "2026-07-01"
verified_date: ""
domain_expert: ""
---


## Problem

AI crawlers take content and send nothing back. Small sites face a Faustian bargain: show up in search and let AI train on you, or risk losing discoverability.

## Root Cause

The 30-year deal between crawlers and website owners (we crawl you, you get referrals) broke with AI. AI presents answers directly, bypassing the referral model.

## Solution

### Cloudflare AI Traffic Control Options

| Option | What It Does |
|--------|-------------|
| **Block AI Bots** | One-click block all known AI crawlers |
| **Pay-Per-Crawl** | Charge per crawl via x402 protocol |
| **AI Search Opt-in** | Allow AI search but require attribution |
| **Monetization Gateway** | Charge for any resource (API, MCP, data) |

### Pay-Per-Crawl Configuration

```bash
# Enable via Cloudflare dashboard or API
# Each crawler gets a price tag
# Payment settles via x402 (stablecoin)

# Example: charge $0.001 per page crawl
curl -X POST "https://api.cloudflare.com/client/v4/zones/{zone_id}/ai-crawl" \
  -H "Authorization: Bearer {token}" \
  -d '{
    "action": "pay_per_crawl",
    "price": "0.001",
    "currency": "USDC"
  }'
```

### Attribution Business Insights

Cloudflare now provides attribution data showing which AI services are crawling your content and how often, enabling data-driven decisions about pricing and blocking.

## Verification

1. Enable "Block AI Bots" on a Cloudflare zone
2. Verify known AI crawlers are blocked (check logs)
3. Enable Pay-Per-Crawl with a price
4. Verify crawlers receive 402 and can pay to access

## Notes

- Small sites benefit most: AI discoverability without losing control
- The "Faustian bargain" problem is real for content creators
- Source: blog.cloudflare.com (2026-07-01)
