---
{
  "title": "Remote search rate limiting: 5 free/day, then registration",
  "domain": "mcp",
  "tags": ["mcp", "rate-limit", "search", "registration", "abuse"],
  "status": "published",
  "evidence_level": "E2",
  "source": "mcp-intake-fb741dcb9d",
  "created": "2026-08-19"
}

provenance:
  source: "unknown"
  contributor: "Ikalus1988"
  merged_at: "2026-08-19"
  evidence: "post-publication"
---

## Problem

Remote HTTP MCP search has no rate limiting, allowing unlimited usage without identification. This enables abuse and provides no usage data.

## Root Cause

The MCP endpoint was designed for open access without considering rate limiting or user identification.

## Solution

Add rate limiting to remote HTTP MCP search:

**Rules:**
- Local stdio MCP: unlimited (user has the code)
- Remote HTTP MCP: ≤5 searches/day per IP
- After 5 searches: return error with registration hint
- With token: unlimited searches

**Implementation:**
```javascript
// Cloudflare Worker KV
const key = `rate:${ip}:${date}`;
const count = await env.MISAKANET_KV.get(key, "number") || 0;
if (count >= 5) {
  return { error: "Rate limit exceeded. Register for unlimited." };
}
await env.MISAKANET_KV.put(key, count + 1, { expirationTtl: 86400 });
```

**Response when limit exceeded:**
```json
{
  "error": "Rate limit: 5 free searches per day exceeded",
  "hint": "Register to get unlimited access: misakanet_register"
}
```

## Verification

- Remote search without token fails after 5/day
- Local stdio search unlimited
- Token holders have unlimited access

## Key Points

- Low barrier to entry (5 free searches)
- Encourages registration for heavy users
- Local users不受限 (they have the code)
- Cloudflare KV handles rate limiting efficiently
