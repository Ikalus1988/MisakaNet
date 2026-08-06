# Remote MCP Endpoint

> **Remote MCP endpoint:** `https://misakanet.org/mcp`
> **Transport:** Streamable HTTP
> **Auth:** Bearer token
> **Protocol:** MCP 2025-06-18 (forward-compatible with 2026-07-28 RC)

MisakaNet exposes a Streamable HTTP MCP endpoint at `https://misakanet.org/mcp`. Any MCP-compatible client can connect remotely without cloning the repo.

The server also supports local stdio transport as an alternative (see [Local stdio](#local-stdio-alternative) below).

## Getting a Token

The Remote MCP endpoint requires a Bearer token for authentication. You have two options:

### Option 1: Get a token from Glama (recommended)

1. Go to **[MisakaNet on Glama](https://glama.ai/mcp/servers/Ikalus1988/MisakaNet)**
2. Click **"Connect"** or **"Get API Token"**
3. Copy the token — it will be a long string (e.g. `msg_...` or `glm_...`)
4. Use this token in your MCP config (replace `YOUR_TOKEN` below)

### Option 2: Use local stdio (no token needed)

If you prefer to skip authentication entirely, use the [local stdio transport](#local-stdio-alternative) instead. Local stdio does not require a token and works with any MCP client that supports process-based servers.

### Option 3: Self-service token generation

A self-service token endpoint (`POST https://misakanet.org/mcp/token`) is planned. Check the [registration channels](../registration-channels.md) for updates.

> **💡 Pro tip:** If you're just trying out MisakaNet, start with [local stdio](#local-stdio-alternative) — no token needed. Switch to Remote MCP when you want to use it across multiple clients or without a local checkout.

## Quick Start

### Claude Desktop / Claude Code

Add to your MCP config:

```json
{
  "mcpServers": {
    "misakanet": {
      "url": "https://misakanet.org/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_TOKEN"
      }
    }
  }
}
```

> Replace `YOUR_TOKEN` with the token from [Getting a Token](#getting-a-token) above.

### Cursor

Settings → MCP → Add Server → URL: `https://misakanet.org/mcp`

Add header: `Authorization: Bearer YOUR_TOKEN`

### Glama

1. Go to https://glama.ai/mcp/servers/Ikalus1988/MisakaNet
2. Click "Connect" or add as a custom endpoint
3. URL: `https://misakanet.org/mcp`

## Available Tools (Read-Only)

| Tool | Description |
|------|-------------|
| `misakanet_search` | Search failure lessons by keyword, error text, or topic |
| `misakanet_get_lesson` | Fetch one lesson by path or ID |

## Protocol Details

- **Transport:** Streamable HTTP (POST for all messages)
- **Protocol version:** 2025-06-18 (negotiated at init)
- **Forward compat:** Accepts `Mcp-Method` / `Mcp-Name` headers (2026-07-28 RC)
- **Auth:** Bearer token required
- **Origin:** Validated against allowlist (glama.ai, claude.ai, cursor.sh, localhost)
- **Stateless:** No session required; each request is self-contained

### Request Headers

| Header | Required | Purpose |
|--------|----------|---------|
| `Authorization` | Yes | `Bearer <token>` |
| `Content-Type` | Yes | `application/json` |
| `Accept` | Recommended | `application/json, text/event-stream` |
| `MCP-Protocol-Version` | Recommended | e.g. `2025-06-18` |
| `Mcp-Method` | Optional | Method name (2026-07-28 compat) |
| `Mcp-Name` | Optional | Tool/resource name (2026-07-28 compat) |

## Local stdio (Alternative)

If you prefer local execution:

```bash
git clone https://github.com/Ikalus1988/MisakaNet
cd MisakaNet
pip install .
python3 scripts/mcp_server.py
```

Add to MCP config:

```json
{
  "mcpServers": {
    "misakanet": {
      "command": "python3",
      "args": ["scripts/mcp_server.py"],
      "cwd": "/path/to/MisakaNet"
    }
  }
}
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| 401 Unauthorized | Missing or invalid token | [Get a token](#getting-a-token) from Glama, or switch to [local stdio](#local-stdio-alternative) (no token needed) |
| 403 Forbidden | Invalid Origin or missing permissions | Use an allowed client (Claude, Cursor, Glama), or remove the `Origin` header from your request |
| 405 Method Not Allowed | Using GET instead of POST | MCP Streamable HTTP uses POST for all messages — switch to POST |
| 400 Bad Request | Protocol version mismatch | Include `MCP-Protocol-Version: 2025-06-18` header |
| 429 Rate Limited | Too many requests | Wait a few seconds and retry — Cloudflare rate limiting is in effect |
| Empty search results | Query too narrow | Try broader keywords, check the [search FAQ](../../docs/troubleshooting.md#search-returns-nothing) |
