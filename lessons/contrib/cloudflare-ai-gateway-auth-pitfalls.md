---
title: "Cloudflare AI Gateway: gateway token ≠ account token, /workers-ai/run/ path required"
domain: devops
tags:
  - cloudflare
  - ai-gateway
  - workers-ai
  - benchmark
  - caching
  - authentication
status: published
created: 2026-09-05 00:00:00 UTC
updated: 2026-09-05 00:00:00 UTC
evidence_level: E2
---

## Problem

When switching Workers AI benchmark calls to Cloudflare AI Gateway (for caching and neuron savings), every request fails with authentication or routing errors:

1. Using the account-level API token (My Profile → API Tokens, even with "AI Gateway: Run" permission) → `401` / error code `10000` Authentication error
2. Using the gateway token but calling `/workers-ai/{model}` → routing error `7003` or auth error `10000`
3. Hours wasted debugging authentication when the real issue was token type AND path mismatch

## Root Cause

1. **AI Gateway's Authenticated mode only accepts a "gateway token"** — created in the specific gateway's Settings page. The token is shown only once at creation; navigating away to "manage API tokens" loses the full value. Account-level API tokens are NOT accepted even with the correct permission scope.

2. **The correct gateway path is `/workers-ai/run/{model}`**, not `/workers-ai/{model}`. The gateway proxies to Workers AI's `/ai/run/{model}` endpoint, so the `run` segment is mandatory.

3. **Error codes distinguish the failure direction**: account token → `401/2009`; invalid gateway token → `10000`; wrong path → `7003`.

## Fix

1. In the AI Gateway Settings page, create an authentication token with "Run" permission. **Copy it immediately** — it cannot be retrieved later.
2. Use the full gateway URL: `https://gateway.ai.cloudflare.com/v1/{account_id}/{gateway_id}/workers-ai/run/@cf/{model}`
3. Set header: `Authorization: Bearer {gateway_token}`
4. Enable "Cache Responses" in gateway settings — identical prompts hit the cache, making weekly benchmark reruns cost near-zero neurons.
5. Free plan: 10,000 neurons/day. Exhaustion returns `429`; resets daily.

## Verification

- Gateway token + `/workers-ai/run/` path → model response (not auth/routing error)
- Second identical prompt → cache hit (response time <50ms, no neuron cost)
- Benchmark script switches via `AI_GATEWAY_ID` / `AI_GATEWAY_TOKEN` env vars successfully
