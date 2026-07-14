# Continue Integration

Give Continue access to 205+ verified failure lessons from MisakaNet.

## Setup

1. Clone MisakaNet:
```bash
git clone https://github.com/Ikalus1988/MisakaNet.git ~/MisakaNet
```

2. Add to `~/.continue/config.json`:
```json
{
  "mcpServers": [
    {
      "name": "misakanet",
      "command": "python3",
      "args": ["~/MisakaNet/scripts/mcp_server.py"]
    }
  ]
}
```

3. Restart VS Code / JetBrains with Continue extension.

## Usage

In Continue's chat, ask:

- "Search MisakaNet for DCO sign-off failure"
- "Find lessons about pip install timeout"
- "What does MisakaNet know about GitHub token issues?"

## Demo Queries

| Query | What you'll get |
|-------|----------------|
| DCO sign-off failed | Fix workflow with `--amend --signoff` |
| pip install timeout | SSL/proxy timeout solutions |
| GitHub token exposed | Secret scanning response pattern |
| database locked | SQLite WAL mode + timeout fix |
| Feishu document cleared | API deletion safety pattern |

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "No MCP server found" | Check path is absolute in config.json |
| "Import error" | `pip install -r ~/MisakaNet/requirements.txt` |
| "No results" | Verify `~/MisakaNet/data/lessons.json` exists |

## Learn More

- [MCP Quickstart](../mcp-quickstart.md)
- [Full MCP docs](../mcp.md)
