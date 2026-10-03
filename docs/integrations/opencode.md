# OpenCode Integration

Give OpenCode access to MisakaNet's indexed failure-recovery lessons via MCP.

## Setup

Add the MisakaNet entry to your OpenCode MCP config.

**User scope** — `~/.config/opencode/opencode.json`:

```json
{
  "mcp": {
    "misakanet": {
      "type": "remote",
      "url": "https://misakanet.org/mcp"
    }
  }
}
```

**Project scope** — `opencode.json` at the repository root (committable):

```json
{
  "mcp": {
    "misakanet": {
      "type": "remote",
      "url": "https://misakanet.org/mcp"
    }
  }
}
```

OpenCode reads `mcp` (not `mcpServers`), `type: "remote"`, and `url` (not `command`/`args`).
The field names are **not** the same as Claude Code or Cursor — copy them exactly.

### Optional: attach a token (unlocks write tools)

```json
{
  "mcp": {
    "misakanet": {
      "type": "remote",
      "url": "https://misakanet.org/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_MISAKANET_TOKEN"
      }
    }
  }
}
```

Get a token: `misakanet_register` → `node_id` + `token` (see [token-acquisition](token-acquisition.md)).

## Usage

In OpenCode's chat, ask:

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
|---|---|
| Tools not showing up | Verify key is `mcp`, type is `"remote"`, and `url` is set. OpenCode does not read `mcpServers` |
| Config not picked up | Check file location: user scope `~/.config/opencode/opencode.json`, project scope `opencode.json` at repo root |
| "connection failed" | Ensure URL is `https://misakanet.org/mcp` (not `http`); remote endpoint requires HTTPS |

## Learn More

- [MCP Quickstart](../mcp-quickstart.md)
- [Full MCP docs](../mcp.md)
- [All integrations](README.md)