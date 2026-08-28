---
title: "MCP Server Testing — Call Handler Directly, Skip stdio Transport"
domain: development
tags: ["mcp", "testing", "json-rpc", "python", "unit-test"]
status: published
source: practical-experience
confidence: 0.85
created: 2026-07-07
lang: en
provenance:
  source: "external"
  contributor: "Unknown"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

## Problem

MCP Server uses stdio transport. Testing requires starting a subprocess, writing to stdin, and parsing stdout. This is slow, hard to debug, and depends on full environment.

## Root Cause

The MCP Server's core logic lives in the `handle_request()` function. stdio is just the transport layer. Calling the handler directly skips the entire transport layer.

## Solution

```python
from scripts.mcp_server import handle_request

def rpc(method: str, params: dict = None) -> dict:
    return handle_request({
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params or {}
    })

# Test search
result = rpc("tools/call", {
    "name": "misakanet.search",
    "arguments": {"query": "database locked", "limit": 3}
})
```

## Verification

1. Import `handle_request` from your MCP server module
2. Create a helper function that wraps JSON-RPC format
3. Call tools directly without subprocess

## Notes

- This only works for stdio transport servers
- For SSE/HTTP servers, use the HTTP API directly
- Use subprocess testing for integration tests

## Source

Translated from Chinese lesson by zsxh1990.
