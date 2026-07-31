# Integrations

Connect MisakaNet to your AI coding tool. Search 207+ lessons directly from your workflow.

## Available Integrations

| Tool | Status | Setup |
|------|--------|-------|
| **Continue.dev** | ✅ Ready | [Setup Guide](continue/README.md) |
| **Claude Code** | ✅ Ready | MCP server — see below |
| **Cursor** | Planned | — |
| **Aider** | Planned | — |
| **VS Code** | Planned | — |
| **Cline** | Planned | — |
| **Shell alias** | Ready | [See plugin + formatted output](../integrations/shell/README.md) |

## Quick: Shell Alias

Add to `~/.bashrc` or `~/.zshrc`:

```bash
misaka() {
  local repo="$HOME/MisakaNet"
  if [ ! -d "$repo" ]; then
    git clone https://github.com/Ikalus1988/MisakaNet.git "$repo"
  fi
  cd "$repo" && pip install -q misakanet-core
  python3 search_knowledge.py "$*" --top 5
}
```

Usage: `misaka database locked`

## Python Integration

```python
from misakanet.tools.langchain_tool import MisakaNetSearchTool

tool = MisakaNetSearchTool()
results = tool._run("database locked")
```

## MCP Server

MisakaNet ships as an MCP server for Claude Code, Cursor, Continue.dev, and any MCP-compatible tool.

### Claude Code Setup

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "misakanet": {
      "command": "python3",
      "args": ["C:/Users/hp/MisakaNet/scripts/mcp_server.py"]
    }
  }
}
```

### Available Tools

| Tool | Description |
|------|-------------|
| `misakanet_search` | Search lessons by query, domain, and top-N |
| `misakanet_get_lesson` | Get full lesson content by path or ID |
| `misakanet_submit_usage` | Report lesson usage (solved/partial/not-helpful) |

### Prerequisites

```bash
# Build SAG-Lite index (one-time)
python3 scripts/export_okf.py
python3 scripts/build_sag_index.py
```

### Usage

Once configured, your AI tool can search MisakaNet directly:
- Claude Code: "search MisakaNet for database locked errors"
- Cursor: `@misaka database locked`
- Any MCP client: call `misakanet_search` tool

---

*Want to build an integration for your tool? See [bounty #268](https://github.com/Ikalus1988/MisakaNet/issues/268).*
