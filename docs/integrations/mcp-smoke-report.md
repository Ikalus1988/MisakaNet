# MisakaNet MCP smoke report

Test date: 2026-08-02
Test version: v2.14.0
Related issue: #761

## Scope

This report verifies the MisakaNet MCP server through local stdio. It is intended as public evidence for users coming from Glama, Cursor, Claude Desktop, Claude Code, or other MCP-compatible clients.

## Environment

- Repository: `C:\Users\hp\MisakaNet`
- Entry point: `scripts/mcp_server.py`
- Transport tested: MCP JSON-RPC over stdio
- Search backend observed: SAG-Lite available, BM25 fallback not available in this local environment

## Smoke commands

The following Python harness starts the stdio server and sends MCP JSON-RPC requests:

```powershell
@'
import json, subprocess, sys
p = subprocess.Popen(
    [sys.executable, 'scripts/mcp_server.py'],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    encoding='utf-8',
)
reqs = [
    {'jsonrpc':'2.0','id':1,'method':'initialize','params':{}},
    {'jsonrpc':'2.0','id':2,'method':'tools/list','params':{}},
    {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'misakanet_search','arguments':{'query':'database locked','top':2}}},
    {'jsonrpc':'2.0','id':4,'method':'tools/call','params':{'name':'misakanet_usage_status','arguments':{}}},
]
for r in reqs:
    p.stdin.write(json.dumps(r) + '\n')
    p.stdin.flush()
    print(p.stdout.readline().strip())
p.kill()
print(p.stderr.read(), file=sys.stderr)
'@ | python -
```

## Verified calls

### `initialize`

Result: passed.

Observed server info:

```json
{"name":"misakanet","version":"2.14.0"}
```

### `tools/list`

Result: passed.

Observed tools:

- `misakanet_search`
- `misakanet_get_lesson`
- `misakanet_submit_usage`
- `misakanet_usage_status`

### `misakanet_search`

Request:

```json
{"name":"misakanet_search","arguments":{"query":"database locked","top":2}}
```

Result: passed.

Expected output shape:

```json
{
  "results": [
    {
      "title": "...",
      "path": "lessons/.../*.md",
      "score": 8.3168
    }
  ],
  "source": "sag-lite"
}
```

Observed top match: `Hermes State Database Lock Issues - Cleanup Protocol`.

### `misakanet_usage_status`

Request:

```json
{"name":"misakanet_usage_status","arguments":{}}
```

Result: passed.

Expected output shape:

```json
{
  "user": "anon:mcp-default",
  "free_reads_used": 0,
  "free_reads_limit": 5,
  "free_reads_remaining": 5,
  "credits": 0,
  "is_registered": false
}
```

## Common failures and fixes

| Failure | Likely cause | Fix |
|---|---|---|
| MCP client cannot start server | Wrong Python command or wrong repo path | Use an absolute path to `scripts/mcp_server.py`; on Windows try `py` or `python` instead of `python3`. |
| Search returns no engine available | SAG index is missing and package fallback is unavailable | Run `python scripts/export_okf.py` and `python scripts/build_sag_index.py`, then restart the MCP client. |
| Client still shows old tools | Client did not reload MCP config | Fully restart Claude Desktop, Cursor, Claude Code, or the MCP inspector. |
| JSON parse errors | Running helper scripts as Python or mixing shell commands with MCP stdio | Start only `scripts/mcp_server.py` as the MCP command; do not run `misaka-search.sh` with Python. |

## Quickstart links

- MCP quickstart: `docs/mcp-quickstart.md`
- Cursor integration: `docs/integrations/cursor-failure-memory.md`
- Claude Code integration: `docs/integrations/claude-code-failure-memory.md`
- Glama analytics boundary: `docs/integrations/glama-analytics.md`
