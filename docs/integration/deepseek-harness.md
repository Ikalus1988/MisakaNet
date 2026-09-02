# DeepSeekHarness Integration

MisakaNet provides a recovery-memory plugin for DeepSeekHarness via MCP.

## Architecture

```
DeepSeekHarness (execution layer)
    ↓ MCP call
MisakaNet DeepSeekHarness Adapter (recovery layer)
    ↓ delegates to
MisakaNet MCP Server (core)
```

The adapter is a thin naming layer — all logic delegates to the existing MCP server.

## Setup

### 1. MCP Server (recommended)

Add to your DeepSeekHarness MCP config:

```json
{
  "mcpServers": {
    "misakanet-recovery": {
      "command": "python3",
      "args": ["/path/to/MisakaNet/scripts/mcp_deepseek_adapter.py"]
    }
  }
}
```

### 2. Available Tools

| Tool | Description |
|------|-------------|
| `deepseek.recovery.search` | Search failure-recovery lessons |
| `deepseek.recovery.get_lesson` | Fetch a specific lesson |
| `deepseek.recovery.submit_feedback` | Record that a lesson helped |
| `deepseek.recovery.status` | Check plugin status |
| `deepseek.recovery.doctor` | Health check |
| `deepseek.recovery.smoke` | Minimal smoke test |

### 3. Usage Examples

#### Search for a failure

```json
{
  "tool": "deepseek.recovery.search",
  "arguments": {
    "query": "pip install timeout SSL error",
    "top": 3
  }
}
```

#### Get a specific lesson

```json
{
  "tool": "deepseek.recovery.get_lesson",
  "arguments": {
    "id": "pip-install-network-timeout-ssl-error-fix"
  }
}
```

#### Health check

```json
{
  "tool": "deepseek.recovery.doctor",
  "arguments": {}
}
```

## Design Principles

1. **MisakaNet = recovery layer** — not a model dialogue layer
2. **Adapter = naming layer** — no logic duplication
3. **Core = all logic** — adapter delegates to existing MCP server
4. **Portable** — adapter can be used with any harness, not just DeepSeekHarness

## Troubleshooting

### Search returns empty results

- Run `python3 scripts/build_sag_index.py` to rebuild the search index
- Check `deepseek.recovery.doctor` for health status

### SQLite keyword errors

Some queries trigger SQLite FTS keyword conflicts (e.g. "off", "and"). Use alternative phrasing or rebuild the index.

### MCP server not starting

- Ensure Python 3.10+ is available
- Check that `scripts/mcp_server.py` exists
- Run `python3 -m py_compile scripts/mcp_server.py` to verify syntax

---

## GitHub topic

This repository is published under the `dsh-plugin` topic as a DeepSeekHarness-compatible recovery-memory MCP adapter.

```
gh repo edit Ikalus1988/MisakaNet --add-topic dsh-plugin --add-topic deepseek-harness
```

**Topics:** `dsh-plugin`, `deepseek-harness`, `mcp`, `mcp-server`, `agent-memory`, `failure-recovery`, `coding-agents`
