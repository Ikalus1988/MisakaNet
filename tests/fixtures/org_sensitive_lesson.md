---
{
  "title": "Internal Xiaomi API rate limiting workaround",
  "domain": "ops",
  "tags": ["xiaomi", "api", "rate-limit"],
  "status": "published",
  "confidence": "0.7",
  "created": "2026-07-01",
  "source": "https://mi.feishu.cn/docs/xxx"
}
---

## Problem

The Xiaomi internal API at mi.feishu.cn returns 429.

## Root Cause

Internal rate limit is 100 req/min for the mify gateway.

## Solution

Add exponential backoff. Use the internal Xiaomi SDK.

## Verification

Tested on internal Xiaomi staging environment.

## Notes

This is specific to Xiaomi's internal infrastructure.
