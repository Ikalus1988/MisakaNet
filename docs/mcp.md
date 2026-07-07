# MisakaNet MCP Server

MisakaNet exposes its lesson knowledge base via the [Model Context Protocol](https://modelcontextprotocol.io/), enabling AI assistants to search and retrieve engineering lessons in real time.

## Quick Start

### 1. Prerequisites

```bash
cd MisakaNet
pip install -r requirements.txt
```

### 2. Test the server

```bash
# Start the MCP server (stdio transport)
python3 scripts/mcp_server.py
```

### 3. Connect from Claude Code

Add to your `~/.claude/settings.json` (or project `.claude/settings.json`):

```json
{
  "mcpServers": {
    "misakanet": {
      "command": "python3",
      "args": ["/path/to/MisakaNet/scripts/mcp_server.py"]
    }
  }
}
```

### 4. Connect from Cursor

Create `.cursor/mcp.json` in your project root:

```json
{
  "mcpServers": {
    "misakanet": {
      "command": "python3",
      "args": ["/path/to/MisakaNet/scripts/mcp_server.py"],
      "env": {}
    }
  }
}
```

### 5. Connect from Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "misakanet": {
      "command": "python3",
      "args": ["/path/to/MisakaNet/scripts/mcp_server.py"]
    }
  }
}
```

## Available Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `misakanet.search` | Search lessons by query | `query` (required), `domain?`, `top?` (default 5) |
| `misakanet.get_lesson` | Get a specific lesson | `path_or_id` (required) |
| `misakanet.submit_usage` | Report lesson usage | `lesson_id` (required), `tool?`, `outcome?` |

## Search Scopes

By default, the server searches **core** and **contrib** lessons only. Drafts are excluded to avoid surfacing unverified content.

## Search Sources

The server uses two search backends (auto-detected):

1. **SAG-Lite** (SQLite) — fast, pre-built index at `data/sag.db`
2. **BM25** (fallback) — real-time search via `misakanet.search.engine`

If neither is available, the server returns an error suggesting index rebuild:

```bash
python3 scripts/build_sag_index.py
```

## Smoke Test

Run the built-in smoke test to verify your setup:

```bash
python3 tests/test_mcp_server.py
```

This tests:
- `search` returns results with `path`, `status`, and `badge` fields
- `get_lesson` returns lesson content
- Default scope excludes drafts
