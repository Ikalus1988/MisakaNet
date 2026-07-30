---
title: "MCP Server Testing — Call Handler Directly, Skip stdio Transport"
domain: development
tags:
  - mcp
  - testing
  - json-rpc
  - python
  - unit-test
status: published
source: practical-experience
confidence: 0.85
created: 2026-07-07
lang: en
---

## Problem

MCP Server uses stdio transport (stdin/stdout JSON-RPC). Testing requires starting a subprocess, writing to stdin, and parsing stdout. This approach:

1. Is slow (requires forking a process)
2. Is hard to debug (stdout mixes protocol messages and logs)
3. Depends on full environment (search index, database, etc.)

## Root Cause

The MCP Server's core logic lives in the `handle_request()` function. stdio is just the transport layer. Calling the handler directly skips the entire transport layer.

## Solution

**Call the JSON-RPC handler directly without starting a subprocess:**

```python
from scripts.mcp_server import handle_request

def rpc(method: str, params: dict = None) -> dict:
    """Send a JSON-RPC request to the handler directly."""
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
print(result)
```

## Verification

1. Import `handle_request` from your MCP server module
2. Create a helper function that wraps JSON-RPC format
3. Call tools directly without subprocess
4. Assert on the response structure

## Notes

- This only works for stdio transport servers
- For SSE/HTTP servers, use the HTTP API directly
- Skip transport layer testing if you only need to test tool logic
- Use subprocess testing for integration tests that need full protocol flow

## Source

Translated from Chinese lesson by zsxh1990.
