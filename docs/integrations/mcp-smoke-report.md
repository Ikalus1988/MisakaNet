# MCP Smoke Report (MisakaNet)

- **Date:** 2026-08-02
- **Version:** v2.14.0
- **Scope:** Local stdio, Docker/GHCR, Claude Desktop / Cursor
## Test Methods
### 1) Local stdio (Python)
- Start MCP server with local entrypoint.
- Connect via MCP client (Claude Desktop / Cursor) using stdio.

### 2) Docker / GHCR
- Pull image from GHCR.
- Run container with required env and volume mounts.

### 3) Claude Desktop / Cursor
- Add MCP config to client JSON.
- Restart client before first tool call.

## Successful Tool Calls
- `misakanet_search`
- `misakanet_usage_status`

### Example Success Query
```
Search MisakaNet for "database locked"
```

## Common Failures + Fixes
1) **Path wrong / binary not found**
   - Fix: verify absolute path in config and reinstall dependencies.

2) **Python not found**
   - Fix: ensure Python is installed and available in PATH.

3) **Missing index**
   - Fix: run the index build script or refresh knowledge base cache.

4) **Client not restarted**
   - Fix: restart Claude Desktop / Cursor after config changes.

## Quickstart Links
- Local setup: `docs/agents/retrieval-and-contribution.md`
- Client config: `docs/agents/node-injection.md`
- Troubleshooting: `docs/agents/retrieval-and-contribution.md`
