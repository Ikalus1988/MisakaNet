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
| `misakanet_search` | Search lessons by query | `query` (required), `domain?`, `top?` (default 5) |
| `misakanet_get_lesson` | Get a specific lesson | `path` or `id` (required) |
| `misakanet_submit_usage` | **[Experimental]** Report lesson usage (local log only) | `lesson_id` (required), `tool?`, `outcome?` |

## Resources

| URI | Description |
|-----|-------------|
| `misaka://lessons/index` | Browse all published lessons (core + contrib) |
| `misaka://protocol/overview` | Swarm Knowledge Protocol config (trust tiers, rings, scoring) |
| `misaka://docs/readme` | Project overview and quickstart |
| `misaka://docs/faq` | Troubleshooting FAQ |
| `misaka://docs/changelog` | Latest release notes |

## Prompts

| Name | Description | Arguments |
|------|-------------|-----------|
| `search_lesson` | Guided lesson search | `query` (required), `domain?` |
| `triage_failure` | Structured failure triage | `error` (required), `context?` |
| `release_audit` | Release readiness check | `version` (required) |

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

## Security & Boundaries

- **Not a skill marketplace.** MisakaNet is a failure memory network — lessons come from real debugging sessions, not curated skill packs.
- **Read-only by default.** Tools like `misakanet_search` and `misakanet_get_lesson` are read-only. `misakanet_submit_usage` is **experimental** and currently logs locally only — no data is sent externally.
- **No raw sensitive content uploaded.** Search queries stay local. Lesson content is public (open-source repo). Usage reports contain only lesson ID + outcome, not source code or error logs.
- **Write operations require explicit confirmation.** If `submit_usage` is extended to create GitHub Issues in the future, it will require user confirmation before submission.

## Glama

MisakaNet is listed on [Glama.ai](https://glama.ai/mcp/servers) for MCP server discovery.

