# Cursor / MCP Integration Setup

## Quick Start

### Option A: MCP Server (recommended)

Add to your Cursor MCP config (Settings → MCP → Add Server):

```json
{
  "mcpServers": {
    "misakanet": {
      "command": "python3",
      "args": ["/path/to/MisakaNet/integrations/mcp-server/server.py"]
    }
  }
}
```

Or copy `integrations/mcp-server/cursor_mcp.json` to your project's `.cursor/mcp.json`.

### Option B: .cursorrules

Copy `.cursorrules` from the MisakaNet repo root to your project. This instructs
Cursor to search MisakaNet when debugging (requires MCP server active).

## Available Tools

| Tool | Description |
|------|-------------|
| `misakanet_search` | Search lessons by query, returns ranked results |
| `misakanet_read_lesson` | Read full lesson content by path |
| `misakanet_list_domains` | List available knowledge domains |

## How It Works

```
Cursor → MCP (stdio JSON-RPC) → server.py → search_knowledge.py → results
```

The MCP server wraps `search_knowledge.py --json` and exposes it as tools.
No external dependencies beyond Python 3.10+ and misakanet-core.

## Auto-suggest Behavior

With `.cursorrules` active, Cursor will:
1. Detect error messages in your conversation
2. Proactively search MisakaNet for matching lessons
3. Suggest battle-tested fixes before generic advice

## Claude Desktop

Same MCP config works in `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "misakanet": {
      "command": "python3",
      "args": ["/path/to/MisakaNet/integrations/mcp-server/server.py"]
    }
  }
}
```

## Troubleshooting

- **"python3 not found"**: Use full path or `python` instead
- **No results**: Ensure `misakanet-core` is installed (`pip install misakanet-core`)
- **Timeout**: Large repos may need >15s; adjust timeout in server.py
