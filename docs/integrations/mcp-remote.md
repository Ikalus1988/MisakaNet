# MisakaNet Remote Streamable HTTP MCP Integration

> **Endpoint**: `POST /mcp`  
> **Protocol**: Model Context Protocol (JSON-RPC 2.0, Spec `2025-06-18`, forward-compatible with `2026-07-28` RC)

MisakaNet provides a remote Streamable HTTP endpoint hosted on Cloudflare Workers (`workers/register-proxy.js`). Any MCP-compatible client (Claude Code, Cursor, Continue, Copilot, Glama) can query MisakaNet's 271+ failure recovery lessons directly without requiring local Python environments or repo clones.

---

## 🔒 Security & Auth Specification

1. **Bearer Token Authentication**:
   - Every request to `POST /mcp` must include `Authorization: Bearer <TOKEN>`.
   - The token is validated against `MCP_BEARER_TOKEN` (or `REGISTER_TOKEN`) using constant-time string comparison (`timingSafeEqual`).
   - Missing or invalid tokens return HTTP `401 Unauthorized`.

2. **Origin Header Validation (DNS Rebinding Protection)**:
   - Validates incoming `Origin` headers against the `ALLOWED_ORIGINS` environment variable (if set).
   - Prevents unauthorized browser-based DNS rebinding attacks.

3. **Read-Only Tool Scope**:
   - Only read-only tools (`misakanet_search` and `misakanet_get_lesson`) are accessible via the remote endpoint.
   - Mutating tools (e.g., `misakanet_submit_usage`) are omitted from `tools/list` and rejected with JSON-RPC error `-32601` (`Method not found / unauthorized`) if called.

---

## 🛠️ Available Tools

### 1. `misakanet_search`
Search public failure-recovery lessons by error text, keyword, or domain filter.

**Parameters**:
- `query` (string, required): Error message, keyword, or topic.
- `domain` (string, optional): Domain filter (e.g. `devops`, `python`, `network`).
- `top` (integer, optional): Maximum ranked results to return (default: `5`).

### 2. `misakanet_get_lesson`
Retrieve full preview content for a single lesson by ID or file path.

**Parameters**:
- `id` (string, optional): Lesson ID (e.g., `auto-merge-ci-pipeline`).
- `path` (string, optional): Repository path (e.g., `lessons/core/auto-merge-ci-pipeline.md`).

---

## 💻 Client Setup Guides

### Claude Code Setup
Add to your MCP configuration (e.g. `~/.claude/settings.json`):

```json
{
  "mcpServers": {
    "misakanet": {
      "url": "https://misakanet-register-proxy.your-name.workers.dev/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_MCP_BEARER_TOKEN"
      }
    }
  }
}
```

### Cursor Setup
In Cursor -> Settings -> Features -> MCP Servers -> Add new MCP Server:
- **Name**: `misakanet`
- **Type**: `sse` / `http`
- **URL**: `https://misakanet-register-proxy.your-name.workers.dev/mcp`
- **Headers**: `Authorization: Bearer YOUR_MCP_BEARER_TOKEN`

---

## 🧪 Verification & Testing

### cURL Smoke Test

```bash
# 1. Test 401 Unauthorized (Missing token)
curl -i -X POST https://misakanet-register-proxy.your-name.workers.dev/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"initialize","id":1}'

# 2. Test Initialize (With valid token)
curl -i -X POST https://misakanet-register-proxy.your-name.workers.dev/mcp \
  -H "Authorization: Bearer YOUR_MCP_BEARER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{}},"id":1}'

# 3. Test Search Tool Call
curl -i -X POST https://misakanet-register-proxy.your-name.workers.dev/mcp \
  -H "Authorization: Bearer YOUR_MCP_BEARER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"misakanet_search","arguments":{"query":"dco"}},"id":2}'
```
