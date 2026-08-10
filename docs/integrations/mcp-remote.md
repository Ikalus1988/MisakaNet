# Remote MCP Endpoint

> **Remote MCP endpoint:** `https://misakanet.org/mcp`
> **Transport:** Streamable HTTP
> **Auth:** Bearer token
> **Protocol:** MCP 2025-06-18 (forward-compatible with 2026-07-28 RC)

MisakaNet exposes a Streamable HTTP MCP endpoint at `https://misakanet.org/mcp`. Any MCP-compatible client can connect remotely without cloning the repo.

The server also supports local stdio transport as an alternative (see [Local stdio](#local-stdio-alternative) below).

## Getting a Token

### Option 1: One-Time Pairing Code (Recommended)

1. Open https://misakanet.org/connect in your browser
2. Click "Generate Code" — get a 6-character code (e.g. `A7K9Q2`)
3. Tell your AI agent: "Connect to MisakaNet MCP using pairing code A7K9Q2"
4. The agent calls `POST /mcp/pair` with the code and gets a 24-hour token
5. Done — the agent can now use `/mcp`

### Option 2: Contact Maintainer

Email bot@misakanet.org or comment on [Discussion #1](https://github.com/Ikalus1988/MisakaNet/issues/1) for a persistent token.

### Option 3: Public Token (Read-Only, Low-Rate)

For quick trials, MisakaNet provides a **public read-only token** with rate-limited access (10 req/min):

```
Authorization: Bearer misakanet-public-readonly
```

> ⚠️ The public token is rate-limited and shared. For production use, request a dedicated token via Option 1 or 2.

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
- **Auth:** Bearer token required (see [Getting a Token](#getting-a-token) above)
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
| 401 Unauthorized | Missing or invalid token | Check your `Authorization` header. See [Getting a Token](#getting-a-token) for how to obtain one. |
| 403 Forbidden | Invalid Origin header or missing permissions | Use an allowed client (Claude, Cursor, Glama). For custom clients, set `Origin: https://misakanet.org` or request access from the maintainer. |
| 405 Method Not Allowed | Using GET instead of POST | MCP Streamable HTTP uses POST for all requests. Switch your HTTP method to POST. |
| 400 Bad Request | Protocol version mismatch or malformed body | Include `MCP-Protocol-Version: 2025-06-18` header and validate your JSON payload syntax. |
| 429 Rate Limited | Too many requests in a short period | Wait 60 seconds before retrying. If using the public token, consider requesting a dedicated token (see [Getting a Token](#getting-a-token)). |
| Empty search results | Query too narrow or topic not covered | Try broader keywords, check spelling, or browse by [topic](https://misakanet.org/topics/). If the topic is missing, [request a lesson](https://github.com/Ikalus1988/MisakaNet/issues/new?template=lesson-request.yml). |
