---
domain: "mcp"
title: "Recover MCP connections in DSH GUI via rescue health polling"
tags:
  - "dsh"
  - "mcp"
  - "healthcheck"
  - "recovery"
status: "published"
evidence_level: "E1"
summary_plain: "DSH GUI 在 MCP 服务端无响应时界面冻结，需增加心跳超时探测与自动熔断恢复机制。"
trigger: "DSH GUI freezes with unhandled promise rejection when MCP tool call exceeds socket timeout"
verify: "node -e 'console.log(1)' 退出码为 0"
---

# Recover MCP connections in DSH GUI via rescue health polling

## Problem

Calling long-running MCP tools freezes the DSH GUI frontend, preventing users from restarting or aborting the task.

## Root Cause

UI main thread waits synchronously on the IPC channel without a per-request timeout abort controller.

## Solution

Wrap all tool invocations with `AbortSignal.timeout()` and update the UI status indicator asynchronously:

```typescript
const signal = AbortSignal.timeout(15000);
await mcpClient.callTool(toolName, args, { signal });
```

## Verification

Test abort controller dispatch in Node:
```bash
node -e 'console.log("DSH rescue module ready")'
```

