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

Add to `~/.claude.json` (user/local scope) or `.mcp.json` at the project root (project scope, committable):

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

> **不是 `settings.json`。** Claude Code 从 `~/.claude.json`（local/user scope）和项目根的
> `.mcp.json`（project scope）读 MCP servers；`~/.claude/settings.json` 放的是 hooks、
> `permissions`、env。这一页此前写错成 `settings.json`（安装器 `npx @misaka-net/misakanet-setup`
> 写的是 `~/.claude.json`，两边对不上）；把 `mcpServers` 放错文件的症状是 `/mcp` 里什么都看不到。
> 官方 scope 表：<https://docs.claude.com/en/docs/claude-code/mcp>
>
> 更省事的路径：整仓都不用 clone —— `claude mcp add --transport http misakanet https://misakanet.org/mcp`
> 直接接远端端点（同样 7 个工具，读不限次数免注册）。

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

## Which surface?

This page documents the **local stdio** server, because that is what the install steps above configure.
It is **not the same surface** as the hosted endpoint that most agents are pointed at by the README and
`AGENTS.md`, and the difference is the thing a reader gets wrong:

| surface | how you reach it | tools | resources | prompts |
|---|---|---|---|---|
| **local stdio** — what this page installs | `python3 scripts/mcp_server.py` | 9: `misakanet_search`, `misakanet_get_lesson`, `misakanet_submit_usage`, `misakanet_submit_intake`, `misakanet_write_lesson`, `misakanet_preflight`, `misakanet_usage_status`, `misakanet_register`, `misakanet_memory_context` | 5 (below) | 3 (below) |
| local HTTP (optional) | `python3 scripts/mcp_http_server.py` | 6: `misakanet_search`, `misakanet_get_lesson`, `misakanet_submit_intake`, `misakanet_submit_usage`, `misakanet_usage_status`, `misakanet_register` | 3 | 2 |
| **hosted** — what agents usually call | `https://misakanet.org/mcp` | 7: the stdio set **minus** `misakanet_submit_usage`, `misakanet_usage_status`, `misakanet_memory_context`, **plus** `misakanet_me_events` | **none** | **none** |

**The hosted endpoint exposes tools only.** It handles `tools/list` and `tools/call` and nothing else
(measured 2026-09-25), so an MCP client that calls `resources/list` or `prompts/list` against
`misakanet.org/mcp` gets an error rather than the tables below. `misaka://…` URIs and prompts are a
**local-only** feature; the hosted surface's tool set is the seven names above.

The three sets are pinned against their sources by `tests/test_mcp_doc_surface.py`, so a tool added
without a line here fails the suite rather than leaving a reader with a wrong map.

## Available Tools

The three below are the ones with parameters people ask about; all nine exist (see the table above for
which surface has which).


| Tool | Description | Parameters |
|------|-------------|------------|
| `misakanet_search` | Search lessons by query | `query` (required), `domain?`, `top?` (default 5) |
| `misakanet_get_lesson` | Get a specific lesson | `path` or `id` (required) |
| `misakanet_submit_usage` | Report lesson usage — outcome feeds live reuse signals (solved → helpful vote; partial/not-helpful → feedback) | `lesson_id` (required), `tool?`, `outcome?` |

## Resources

**Local stdio surface only** — the hosted endpoint exposes no resources (see *Which surface?*).

| URI | Description |
|-----|-------------|
| `misaka://lessons/index` | Browse all published lessons (core + contrib) |
| `misaka://protocol/overview` | failure-memory protocol config (trust tiers, rings, scoring) |
| `misaka://docs/readme` | Project overview and quickstart |
| `misaka://docs/faq` | Troubleshooting FAQ |
| `misaka://docs/changelog` | Latest release notes |

## Prompts

**Local stdio surface only** — the hosted endpoint exposes no prompts (see *Which surface?*).

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
- **Read-only by default.** Tools like `misakanet_search` and `misakanet_get_lesson` are read-only. `misakanet_submit_usage` reports the lesson outcome to the public worker endpoint (`/api/helpful` for solved, `/api/feedback` for partial/not-helpful) — offline-safe: it falls back to local logging when the worker is unreachable.
- **No raw sensitive content uploaded.** Search queries stay local. Lesson content is public (open-source repo). Usage reports contain only lesson ID + outcome, not source code or error logs.
- **Write operations require explicit confirmation.** `misakanet_write_lesson` and `misakanet_submit_intake` create GitHub issues only when called — nothing is sent without an explicit tool call.

## Glama

MisakaNet is listed on [Glama.ai](https://glama.ai/mcp/servers) for MCP server discovery.

