---
title: "Cloudflare Worker Programmatic Deploy: Three Pitfalls — Sandbox Egress, 32KB Limit, multipart Content-Type"
domain: "devops"
tags: ["cloudflare", "workers", "deploy", "mcp", "multipart", "kv", "sandbox"]
status: "published"
source: "intake-issue-1305"
created: "2026-08-27"
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

# Cloudflare Worker Programmatic Deploy: Three Pitfalls

## Problem

Deploying large modular Workers via Cloudflare MCP execute encounters three limitations:
1. Execute sandbox fetch to raw.githubusercontent.com / api.github.com returns 403 Forbidden (only Cloudflare internal domains allowed)
2. bash/execve single argument max 32KB (MAX_ARG_STRLEN), 93KB code embedded directly causes "Argument list too long"
3. Multipart upload modules with Content-Type application/javascript cause Cloudflare to parse as classic script, ESM export syntax throws "SyntaxError: Unexpected token export"

## Root Cause

1. Cloudflare execute sandbox has outbound domain whitelist — external code sources (GitHub raw/API) are blocked
2. Linux execve has 32KB hard limit on single argv parameter, mcporter call's code parameter can't carry large code
3. Workers upload API uses multipart part Content-Type to distinguish module format — modules must use `application/javascript+module`, using `application/javascript` treats as plain script, ESM export syntax errors

## Solution

1. **Base64 encode and chunk code** (each chunk ≤24KB) via execute into KV namespace (`storage/kv/namespaces/{ns}/values/{key}`, body is raw text)
2. **Second execute reads back all chunks from KV**, atob decodes and concatenates
3. **Construct multipart/form-data** (metadata part with main_module/compatibility_date/bindings, module part Content-Type must be `application/javascript+module`), PUT `/accounts/{acct}/workers/scripts/{name}` to upload
4. **Verify**: After deploy, curl endpoint to confirm entry_point and handler are active

## Verification

```bash
# Deploy worker
curl -X PUT "https://api.cloudflare.com/client/v4/accounts/{acct}/workers/scripts/misakanet-register-proxy" \
  -H "Authorization: Bearer {token}" \
  -F 'metadata={"main_module":"register-proxy-sw.js","compatibility_date":"2024-01-01","bindings":[]}' \
  -F 'register-proxy-sw.js=@worker.js;type=application/javascript+module'

# Verify deployment
curl -s "https://api.cloudflare.com/client/v4/accounts/{acct}/workers/scripts/misakanet-register-proxy" \
  -H "Authorization: Bearer {token}" | jq '.result.id'

# Test endpoint
curl -X POST https://misakanet.org/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'
```

**Expected Output:**
```json
{"result": {"id": "register-proxy-sw.js", "handlers": ["fetch", "scheduled"]}}
{"jsonrpc":"2.0","id":1,"result":{"serverInfo":{"name":"misakanet"}}}
```
