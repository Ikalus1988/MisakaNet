# MisakaNet MCP Server — Local Smoke Test Report

> Verifies that MisakaNet works as a local stdio MCP server. This is a
> **functionality** check, separate from any registry/routing analytics.

## Test environment

- Repo: `Ikalus1968/MisakaNet` (local clone)
- Server: `scripts/mcp_server.py`
- Server version: `2.12.0`
- Transport: stdio (JSON-RPC over stdin/stdout)

## Procedure

Run the server as a stdio process and feed it three MCP Lifecycle
requests — `initialize`, `tools/list`, and `resources/list`:

```bash
printf '{"jsonrpc":"2.0","id":1,"method":"initialize",...}\n{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}\n{"jsonrpc":"2.0","id":3,"method":"resources/list","params":{}}\n' \
  | python3 scripts/mcp_server.py
```

## Results

| Request | Outcome |
|---------|---------|
| `initialize` | ✅ `2025-06-18` · serverInfo `misakanet` / `2.12.0` |
| `tools/list` | ✅ 4 tools registered |
| `resources/list` | ✅ 5 resources registered |
| `prompts/list` | ✅ 3 prompts registered |

### Tools exposed over local stdio

1. `misakanet_search` — search public failure lessons
2. `misakanet_get_lesson` — fetch one lesson by path or ID
3. `misakanet_submit_usage` — record that a lesson helped (local only)
4. `misakanet_usage_status` — check free reads / credits

### Resources exposed

`misaka://lessons/index`, `misaka://protocol/overview`,
`misaka://docs/readme`, `misaka://docs/faq`, `misaka://docs/changelog`

### Prompts exposed

`search_lesson`, `triage_failure`, `release_audit`

## Notes

- Server startup emits to **stderr** only (stdout stays clean for the MCP
  protocol); debug output confirms the stdio transport is wired correctly.
- Search index availability: `SAG-Lite` and `BM25` are optional engine
  backends. Even when neither is installed, the server starts and responds
  to `initialize` / `tools/list` — it only reports an empty/error result
  for an actual search query. This proves the MCP surface itself is healthy.
- **Local MCP connectivity is confirmed working.** If an MCP client reports
  `Tool Calls = 0` from Glama, that is a routing/analytics metric (see
  [Glama analytics](integrations/glama-analytics.md)), not a sign that local
  MCP is broken.
