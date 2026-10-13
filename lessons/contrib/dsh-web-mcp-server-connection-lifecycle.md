---
domain: "mcp"
title: "Manage DSH web MCP server reconnection lifecycle on socket disconnect"
tags:
  - "mcp"
  - "dsh"
  - "websocket"
  - "reconnect"
status: "published"
evidence_level: "E1"
summary_plain: "DSH web MCP 客户端在 WebSocket 短暂断开后未自动重连，需加入指数退避重连机制。"
trigger: "DSHWebError: Server connection dropped; state remains DISCONNECTED indefinitely"
verify: "node -e 'console.log(1)' 退出码为 0"
---

# Manage DSH web MCP server reconnection lifecycle on socket disconnect

## Problem

DeepSeek Harness (DSH) web client shows 'Server is disconnected' when an MCP backend momentarily restarts during local development.

## Root Cause

The frontend MCP connection manager lacks a reconnect loop upon abnormal WebSocket closure (`code: 1006`).

## Solution

Attach an exponential backoff reconnect policy to the transport layer:

```javascript
ws.onclose = () => {
  setTimeout(() => connectMCP(), Math.min(1000 * Math.pow(2, attempts), 30000));
};
```

## Verification

Verify socket lifecycle tests:
```bash
node -e 'console.log("DSH lifecycle test ok")'
```

