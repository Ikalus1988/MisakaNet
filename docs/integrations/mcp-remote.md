# Remote MCP Endpoint

> **Remote MCP endpoint:** `https://misakanet.org/mcp`
> **Transport:** Streamable HTTP
> **Auth:** Bearer token
> **Protocol:** MCP 2025-06-18 (forward-compatible with 2026-07-28 RC)

MisakaNet exposes a Streamable HTTP MCP endpoint at `https://misakanet.org/mcp`. Any MCP-compatible client can connect remotely without cloning the repo.

The server also supports local stdio transport as an alternative (see [Local stdio](#local-stdio-alternative) below).

## Getting a Token

To use the remote MCP endpoint, you need a Bearer token. Here's how:

1. **Register** — The token is provisioned automatically when you register as a MisakaNet node. See the [registration flow](https://github.com/Ikalus1988/MisakaNet#-setup--registration) for details.
2. **Check CI** — After registration, a CI workflow creates your node entry. You'll receive your token and Misaka ID once it completes (typically within a few minutes).
3. **Alternative: Glama** — If you're using [Glama](https://glama.ai/mcp/servers/Ikalus1988/MisakaNet), you can connect without a token — Glama handles auth automatically.
4. **Contact maintainer** — If you're blocked, open an issue or reach out via the [MisakaNet community](https://github.com/Ikalus1988/MisakaNet).

> ⚠️ **First-time contributors:** The registration → CI → token pipeline may take a few minutes. If your registration CI fails, check that you've filled in all required fields — missing data is the most common cause.

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

## Available Tools

| Tool | Description |
|------|-------------|
| `misakanet_search` | Search failure lessons by keyword, error text, or topic |
| `misakanet_get_lesson` | Fetch one lesson by path or ID |
| `misakanet_submit_usage` | Submit usage feedback for a lesson |
| `misakanet_usage_status` | Check your usage quota and remaining credits |

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
| 401 Unauthorized | Missing or invalid token | [Get a token](#getting-a-token) via registration, or use Glama for auto-auth |
| 403 Forbidden | Invalid Origin header | Use an allowed client (Claude, Cursor, Glama) or remove the Origin header. If your client is new, request allowlist addition. |
| 405 Method Not Allowed | Using GET instead of POST | MCP Streamable HTTP uses POST for all messages |
| 400 Bad Request | Protocol version mismatch | Include `MCP-Protocol-Version: 2025-06-18` header |
| 429 Rate Limited | Too many requests | Wait and retry; check your quota with `misakanet_usage_status` |
| Empty search results | Query too narrow | Try broader keywords, or browse the [lessons index](https://misakanet.org) |

> 💡 **Stuck on auth?** The #1 blocker reported by new users is token acquisition. Start with the [Getting a Token](#getting-a-token) section above. If your registration CI failed, open an issue with the CI run URL — the maintainer can help.
