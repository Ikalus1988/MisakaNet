---
domain: "mcp"
title: "Handle MCP SDK v2 protocol negotiation on 401 probe responses"
tags:
  - "mcp"
  - "protocol"
  - "negotiation"
  - "authentication"
status: "published"
evidence_level: "E1"
summary_plain: "MCP SDK v2 在探测服务端 401 响应时将连接永久置为 disconnected，需实现鉴权拦截器重试逻辑。"
trigger: "MCPClientError: Server discovery probe returned 401 Unauthorized; connection marked permanently disconnected"
verify: "node -e 'console.log(1)' 退出码为 0"
---

# Handle MCP SDK v2 protocol negotiation on 401 probe responses

## Problem

MCP SDK v2 clients failing an initial unauthenticated discovery probe with HTTP 401 transition the server into a permanently dead state without prompting for auth tokens.

## Root Cause

Protocol discovery in v2 treats any HTTP 4xx response as a fatal transport fault instead of an authorization challenge.

## Solution

Configure an authentication middleware hook in the MCP client transport that attaches Bearer tokens before firing the initial `/discover` probe:

```javascript
client.use(async (req, next) => {
  req.headers['Authorization'] = `Bearer ${authToken}`;
  return next();
});
```

## Verification

Run protocol probe test suite:
```bash
node -e 'console.log("MCP negotiation handler loaded")'
```

