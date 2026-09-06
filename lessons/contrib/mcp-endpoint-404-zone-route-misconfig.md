---
title: 'MCP Endpoint 404: Zone Route Points to Worker Without MCP Implementation'
domain: devops
tags:
- cloudflare
- workers
- routes
- mcp
- '404'
- diagnosis
status: published
created: '2026-08-27'
source: intake-issue-1307
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

# MCP Endpoint 404: Zone Route Points to Worker Without MCP Implementation

## Problem

POST https://misakanet.org/mcp returns 404 {"error":"Not found"}, but GET /mcp returns the worker's HTML info page. The symptoms are contradictory. Additionally, /api/lessons returns 502 (GitHub API 401) while /api/counter works normally.

## Root Cause

1. Zone workers routes: `misakanet.org/mcp` and `/mcp/*` point to `misakanet-api` worker, which doesn't have MCP implementation (POST /mcp hits its 404 branch)
2. GET /mcp HTML comes from `misakanet-api` forwarding the register-proxy page, creating contradictory symptoms
3. The live `misakanet-register-proxy` worker is deployed with old code (only `/api/*`, POST /) without `/mcp` routes
4. `/api/lessons` 401 comes from `misakanet-api`'s own REGISTER_TOKEN being expired, while `/api/counter` works because it reads from KV

## Solution

1. Use `PUT /zones/{zone_id}/workers/routes/{route_id}` to change `/mcp` and `/mcp/*` routes to the worker with full MCP implementation (`misakanet-register-proxy`)
2. Redeploy the worker with latest code
3. Consolidate architecture: move `/api/*`, `/ping` routes to the new worker (its new `/api/lessons` uses public raw reads, no longer depending on expired GitHub token)
4. Note: PATCH reports 10405 Method not allowed when using OAuth token for zone route changes — must use PUT instead

## Verification

```bash
# Test MCP endpoint
curl -X POST https://misakanet.org/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'

# Test tools/list
curl -X POST https://misakanet.org/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'

# Test API endpoints
curl -s https://misakanet.org/api/lessons | head -1
curl -s https://misakanet.org/api/counter
curl -s https://misakanet.org/api/health
curl -s https://misakanet.org/ping
```

**Expected Output:**
```json


192

pong
```