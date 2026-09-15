# Integration Status

> Last updated: 2026-09-15

## MCP Registries

| Registry | Status | URL |
|---|---|---|
| Glama | ✅ Listed, MCP indexed | https://glama.ai/mcp/servers/Ikalus1988/MisakaNet |
| MCP Registry | ✅ Listed | https://modelcontextprotocol.io |
| MCP Toplist | ✅ Badge live | https://mcptoplist.com/server/io.github.Ikalus1988%2Fmisakanet |

## IDE Integrations

| IDE | Integration | Status |
|---|---|---|
| Cursor | Failure-memory rule (.cursor/rules/) | ✅ Supported |
| Claude Code | Failure playbook + SKILL.md | ✅ Supported |
| Codex | MCP + AGENTS.md | ✅ Supported |

> **How the Codex row is checked** (codex-cli 0.154.0, 2026-09-15 — re-run these, don't
> take the table's word for it):
>
> ```bash
> codex mcp list              # → misakanet | https://misakanet.org/mcp | enabled | Bearer token
> codex doctor                # → config.toml parse ok · MCP servers 1 · 1 streamable_http · 0 disabled
> codex debug prompt-input "" # → a `# AGENTS.md instructions` item carrying the rule block
> ```
>
> The third one is the interesting one: it renders what the model will actually see, so it
> proves the user-level `~/.codex/AGENTS.md` block reaches the prompt rather than merely
> existing on disk. Codex has no user-level lifecycle hook (0.154.0 hooks are admin-managed
> through `requirements.toml`), so the round-20 checkpoint reminder is rule-driven there,
> not hook-driven.
| DeepSeek Harness | MCP adapter | ✅ Supported |
| Gemini CLI | MCP | ✅ Supported |
| Windsurf | MCP | ✅ Supported |
| OpenCode | MCP | ✅ Supported |
| Copilot | MCP | ✅ Supported |

## Other

| Integration | Status | Notes |
|---|---|---|
| Smithery | ⏸ Paused | Pending upstream changes |
