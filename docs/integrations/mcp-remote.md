# Remote MCP endpoint (`POST /mcp`)

Connect any MCP-compatible client to MisakaNet **without cloning the repo**. The
endpoint runs on the existing Cloudflare Worker (`misakanet-register-proxy`) and
speaks [Streamable HTTP](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports)
(protocol `2025-06-18`, forward-compatible with the `2026-07-28` RC).

- **Endpoint**: `https://misakanet.org/mcp`
- **Transport**: Streamable HTTP (single `POST`, JSON responses, stateless — no session ID)
- **Auth**: `Authorization: Bearer <MCP_TOKEN>`
- **Phase 1 scope**: read-only — `misakanet_search`, `misakanet_get_lesson`

> Prefer running locally? The stdio server (`scripts/mcp_server.py`) is still
> supported and exposes the same two read tools plus resources and prompts —
> see [mcp-quickstart.md](../mcp-quickstart.md).

## Tools

| Tool | Input | Returns |
|------|-------|---------|
| `misakanet_search` | `query` (required), `domain`, `top` (default 5, max 20) | Ranked lesson summaries: `id`, `title`, `domain`, `tags`, `status`, `path`, `score` |
| `misakanet_get_lesson` | `path` **or** `id` | Lesson markdown (`content`, truncated at 5000 chars, plus `length` and `truncated`) |

Both tools are read-only: no writes, no issue creation, no telemetry beyond the
Worker's request log. `misakanet_submit_usage` / `misakanet_usage_status` remain
Phase 2 and are intentionally absent.

## Client configuration

### Claude Code

```bash
claude mcp add --transport http misakanet https://misakanet.org/mcp \
  --header "Authorization: Bearer $MCP_TOKEN"
```

### Claude Desktop / Cursor / Copilot (`mcp.json`)

```json
{
  "mcpServers": {
    "misakanet": {
      "type": "http",
      "url": "https://misakanet.org/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_MCP_TOKEN"
      }
    }
  }
}
```

- **Cursor**: `~/.cursor/mcp.json` (global) or `.cursor/mcp.json` (per project)
- **Claude Desktop**: `claude_desktop_config.json`
- **Copilot (VS Code)**: `.vscode/mcp.json`, under `"servers"` instead of `"mcpServers"`

### Clients without native HTTP transport

```json
{
  "mcpServers": {
    "misakanet": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://misakanet.org/mcp",
               "--header", "Authorization: Bearer YOUR_MCP_TOKEN"]
    }
  }
}
```

### First call to try

> Search MisakaNet for lessons about "database is locked", then open the top result.

## Verify with curl

```bash
export MCP_TOKEN=...   # ask a maintainer, or use your own deployment's secret

# 1. initialize — negotiates the protocol version, returns serverInfo
curl -sS -X POST https://misakanet.org/mcp \
  -H "Authorization: Bearer $MCP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18"}}'

# 2. tools/list — the two read-only tools
curl -sS -X POST https://misakanet.org/mcp \
  -H "Authorization: Bearer $MCP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'

# 3. tools/call — ranked search results
curl -sS -X POST https://misakanet.org/mcp \
  -H "Authorization: Bearer $MCP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"misakanet_search","arguments":{"query":"database locked"}}}'

# 4. tools/call — full lesson markdown
curl -sS -X POST https://misakanet.org/mcp \
  -H "Authorization: Bearer $MCP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"misakanet_get_lesson","arguments":{"id":"auto-merge-ci-pipeline"}}}'
```

Negative checks:

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X POST https://misakanet.org/mcp \
  -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'      # 401

curl -s -o /dev/null -w '%{http_code}\n' -X POST https://misakanet.org/mcp \
  -H "Authorization: Bearer $MCP_TOKEN" -H "Origin: https://evil.example" \
  -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'      # 403

curl -s -o /dev/null -w '%{http_code}\n' https://misakanet.org/mcp                             # 405 (Accept-Post: application/json)
```

## Status codes

| Situation | Status | Body |
|-----------|--------|------|
| Valid request | `200` | JSON-RPC result |
| Notification (`notifications/*`) | `202` | empty |
| Missing / invalid Bearer token | `401` | JSON-RPC error `-32001`, `WWW-Authenticate: Bearer` |
| Origin present but not allowlisted | `403` | JSON-RPC error `-32000` |
| `GET` / `DELETE /mcp` | `405` | `Accept-Post: application/json`, `Allow: POST, OPTIONS` |
| Body over 64 KB | `413` | JSON-RPC error `-32600` |
| Malformed JSON | `400` | JSON-RPC error `-32700` |
| JSON-RPC batch array | `400` | `-32600` (batching was removed in `2025-06-18`) |
| Unknown method / unknown tool | `200` | `-32601` / `-32602` |
| `MCP_TOKEN` not configured on the Worker | `503` | JSON-RPC error `-32000` |

Tool-level problems (missing `query`, lesson not found, GitHub upstream failure)
come back as a normal `200` result with `isError: true`, per the MCP spec.

## Security model

- **Bearer token** — compared in constant time against the `MCP_TOKEN` secret.
- **Origin allowlist** — DNS rebinding protection. Requests with *no* `Origin`
  header (curl, native MCP hosts) are allowed; a request carrying an unknown
  `Origin` is rejected with `403`. Defaults: `misakanet.org`, `www.misakanet.org`,
  `ikalus1988.github.io`, `glama.ai`, `claude.ai`, `cursor.com`. Add more with the
  optional `MCP_ALLOWED_ORIGINS` variable (comma-separated).
- **Path confinement** — `misakanet_get_lesson` only serves `lessons/**/*.md`;
  traversal (`..`) and any other path are rejected before a GitHub request is made.
- **Read-only** — no endpoint in this phase mutates repository or KV state.

## Operating the endpoint

Secrets on the `misakanet-register-proxy` Worker:

| Name | Required | Purpose |
|------|----------|---------|
| `MCP_TOKEN` | yes | Bearer token clients must present. Without it, `/mcp` returns `503`. |
| `REGISTER_TOKEN` | yes (already set) | GitHub PAT used to read `lessons.json` and lesson markdown. |
| `MCP_VERSION` | no | Reported as `serverInfo.version`; defaults to the packaged `pyproject.toml` version. |
| `MCP_ALLOWED_ORIGINS` | no | Extra allowlisted origins, comma-separated. |

```bash
npx wrangler secret put MCP_TOKEN --name misakanet-register-proxy
```

Deploy: pushing `workers/register-proxy-sw.js` to `main` triggers
[`deploy-worker.yml`](../../.github/workflows/deploy-worker.yml).

Lesson data is read through the existing GitHub proxy with the same 30-second KV
cache as `GET /api/lessons` (`lessons.json` from the `data` branch, lesson markdown
from `main`), so MCP traffic adds no extra GitHub API load in the common case.

## Tests

```bash
node --test workers/mcp-remote.test.mjs     # transport, auth, tools, ranking
pytest tests/test_mcp_remote_worker.py      # route/contract checks + the node suite
```

## Troubleshooting

| Symptom | Cause |
|---------|-------|
| `401` with a token you believe is right | Token mismatch — the comparison is exact, including whitespace. Re-set the secret. |
| `403` from a browser-based client | The client's `Origin` is not allowlisted; add it to `MCP_ALLOWED_ORIGINS`. |
| `503` | `MCP_TOKEN` is not set on the Worker. |
| Empty `results` | No lesson matched. Try fewer / more specific keywords, or drop the `domain` filter. |
| `Upstream failure: GitHub API 4xx` | `REGISTER_TOKEN` expired or lost read access. |

## Related

- [Glama Analytics counting boundary](glama-analytics.md) — why "0 routed tool calls" is a measurement gap, and what this endpoint changes
- [MCP smoke report](mcp-smoke-report.md) — local stdio evidence
- [Integrations index](README.md)
