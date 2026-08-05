# MCP Quickstart — Use MisakaNet in Cursor / Claude Desktop / Claude Code

Give your AI coding assistant access to 271 indexed failure-recovery lessons from real debugging sessions.

## What you get

When your agent encounters an error, it can search MisakaNet for known fixes before wasting time re-debugging:

```
You: "My pip install keeps timing out on WSL"
Agent: *searches MisakaNet* → finds pip-install-timeout-ssl lesson → applies fix
```

## Copy this to your coding agent

Paste this into Cursor, Claude Code, or Claude Desktop to install and test MisakaNet in one shot:

```
Please install and test MisakaNet as an MCP failure-memory server.

1. Clone https://github.com/Ikalus1988/MisakaNet
2. Configure it as an MCP stdio server:
   - Command: python3
   - Args: /path/to/MisakaNet/scripts/mcp_server.py
3. Restart your MCP client (Cursor / Claude Code / Claude Desktop)
4. Run the first query: Search MisakaNet for "database locked"
5. Confirm that misakanet_search returns failure-recovery lessons with title, score, and path.
```

MisakaNet is a failure-memory and recovery layer for coding agents / MCP clients. Local stdio MCP calls work independently of Glama analytics.

## Setup

### Claude Code

Add to `.claude/settings.json` in your project:

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

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

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

### Cursor

Add to `.cursor/mcp.json` in your project:

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

### Docker / GHCR

No local Python setup needed — pull the container and run:

```bash
docker pull ghcr.io/ikalus1988/misakanet:2.15.0
docker run -i ghcr.io/ikalus1988/misakanet:2.15.0
```

Or use in MCP config:

```json
{
  "mcpServers": {
    "misakanet": {
      "command": "docker",
      "args": ["run", "-i", "ghcr.io/ikalus1988/misakanet:2.15.0"]
    }
  }
}
```

## Prerequisites

```bash
cd /path/to/MisakaNet
pip install -r requirements.txt
```

## Smoke test

```bash
# Verify the server starts
python3 scripts/mcp_server.py --help

# Test search directly
python3 search_knowledge.py "DCO sign-off"
```

## Demo queries

Once connected, try these in your AI assistant:

| Query | What you'll find |
|-------|-----------------|
| "Search MisakaNet for DCO sign-off failure" | DCO quickfix workflow |
| "Find lessons about GitHub token issues" | PAT, credential helper, auth failures |
| "What does MisakaNet know about pip timeout?" | SSL/proxy timeout fixes |
| "Search for FANUC error codes" | Industrial robot debugging lessons |
| "Find feishu API integration issues" | Feishu/Lark API pitfalls |

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "No MCP server found" | Check path in config is absolute |
| "Import error" | Run `pip install -r requirements.txt` |
| "No results" | Verify `data/lessons.json` exists and is valid |
| Windows encoding error | Set `PYTHONUTF8=1` or use `python3 -X utf8` |

## Learn more

- [Full MCP docs](mcp.md)
- [CLI reference](cli-reference.md)
- [Agent quickstart](quickstart.md)
