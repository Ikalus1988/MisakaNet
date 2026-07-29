# MisakaNet MCP Server

A Model Context Protocol server that exposes MisakaNet lesson search to AI tools.

## Compatible Clients

- Cursor (via MCP settings)
- Claude Desktop (via claude_desktop_config.json)
- Continue.dev (via MCP config)
- Any MCP-compatible client

## Run

```bash
python3 integrations/mcp-server/server.py
```

The server communicates via stdio (JSON-RPC). It does not listen on a port.

## Tools

- `misakanet_search(query, top_k, domain)` — search lessons
- `misakanet_read_lesson(path)` — read full lesson
- `misakanet_list_domains()` — list knowledge areas

## Requirements

- Python 3.10+
- misakanet-core (`pip install misakanet-core`)
- MisakaNet repo cloned locally
