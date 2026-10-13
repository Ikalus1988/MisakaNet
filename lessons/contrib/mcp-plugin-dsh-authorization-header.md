---
domain: "mcp"
title: "Configure Authorization bearer header in DeepSeek Harness MCP plugin configuration"
tags:
  - "mcp"
  - "dsh"
  - "authorization"
  - "bearer-token"
  - "model-context-protocol"
status: "published"
evidence_level: "E1"
summary_plain: "DSH 的 MCP 插件默认配置缺少 Authorization 请求头会导致私有端点报 401 未授权。"
trigger: "DSH plugin default MCP config missing Authorization header 401"
verify: "mcp-validator test-auth-header exits with code 0"
---

# Configure Authorization bearer header in DeepSeek Harness MCP plugin configuration

## Problem

The default configuration generated for the MisakaNet DSH (DeepSeek Harness) MCP plugin omits the `Authorization: Bearer <token>` header, causing authentication failures (HTTP 401 Unauthorized) when communicating with secured endpoints.

## Root Cause

The template manifest used by the plugin generator did not include headers configuration in the client environment dictionary.

## Solution

Specify explicit authorization headers in the plugin's `mcp.json` or `config.yaml`:

### Step 1: Update MCP server configuration
```json
{
  "mcpServers": {
    "misakanet": {
      "command": "node",
      "args": ["packages/mcp-server/dist/index.js"],
      "env": {
        "MISAKANET_AUTH_TOKEN": "${MISAKANET_TOKEN}"
      },
      "headers": {
        "Authorization": "Bearer ${MISAKANET_TOKEN}"
      }
    }
  }
}
```

## Verification

Launch DSH with the updated configuration and verify tool enumeration completes successfully without 401 errors.
