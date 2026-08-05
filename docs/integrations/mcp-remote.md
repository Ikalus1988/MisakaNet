# Remote MCP Endpoint (Streamable HTTP)

Connect any MCP-compatible AI client (Glama, Claude Code, Cursor, GitHub Copilot) directly to MisakaNet via remote Streamable HTTP without cloning the repository or running a local server.

---

## Endpoint Details

- **URL**: `https://misakanet.org/mcp` (or your Cloudflare Worker URL `POST /mcp`)
- **Protocol**: MCP Streamable HTTP Transport (2025-06-18, forward-compatible with 2025-07-28 RC)
- **Authentication**: Bearer Token via `Authorization: Bearer $MCP_TOKEN` header
- **Access Level**: Phase 1 Read-Only (`misakanet_search` + `misakanet_get_lesson`)

---

## Environment & Secrets

| Variable | Type | Description |
|----------|------|-------------|
| `MCP_TOKEN` | Secret | Bearer token for authenticating remote MCP client requests |
| `MCP_VERSION` | Secret (Optional) | Server version reported in `initialize` (defaults to `1.0.0` or package version) |

---

## Available Read-Only Tools

### 1. `misakanet_search`
Search MisakaNet failure-recovery lessons by query keywords, optional domain filter, and top-N limit.

- **Arguments**:
  - `query` (string, required): Error message or search keywords (e.g. `"database locked"`)
  - `domain` (string, optional): Specific domain filter (e.g. `"database-lock"`, `"github-auth"`)
  - `top` (number, optional): Maximum number of results to return (default: `5`)

### 2. `misakanet_get_lesson`
Retrieve full lesson markdown content by path or ID.

- **Arguments**:
  - `path` (string, optional): Lesson path (e.g. `"lessons/core/database_locked.md"`)
  - `id` (string, optional): Lesson ID (e.g. `"database_locked"`)

---

## Verification & Usage Examples

### 1. Initialize

```bash
curl -X POST https://misakanet.org/mcp \
  -H "Authorization: Bearer $MCP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18"}}'
```

### 2. List Available Tools

```bash
curl -X POST https://misakanet.org/mcp \
  -H "Authorization: Bearer $MCP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
```

### 3. Call Search Tool

```bash
curl -X POST https://misakanet.org/mcp \
  -H "Authorization: Bearer $MCP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"misakanet_search","arguments":{"query":"database locked"}}}'
```

### 4. Call Get Lesson Tool

```bash
curl -X POST https://misakanet.org/mcp \
  -H "Authorization: Bearer $MCP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"misakanet_get_lesson","arguments":{"path":"lessons/core/auto-merge-ci-pipeline.md"}}}'
```

---

## Client Integration Setup

### Glama & Remote Clients

Set the remote endpoint in Glama or Cursor remote configuration:

```json
{
  "mcpServers": {
    "misakanet-remote": {
      "url": "https://misakanet.org/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_MCP_TOKEN"
      }
    }
  }
}
```

---

## Security & Origin Validation

- **DNS Rebinding Protection**: Requests containing an `Origin` header are validated against an allowed origin list (`misakanet.org`, `glama.ai`, `cursor.sh`, `claude.ai`, `github.com`, `localhost`).
- **Timing-Safe Auth**: Token comparisons use `timingSafeEqual` to prevent timing side-channel attacks.
- **GET Request Restriction**: Sending `GET /mcp` returns HTTP `405 Method Not Allowed` with `Accept: POST` header.
