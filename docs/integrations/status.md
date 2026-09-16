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
>
> **A live session calls the tool** (2026-09-15, codex-cli 0.154.0 driven by MiniMax-M3):
>
> ```bash
> MINIMAX_API_KEY=… codex exec --json >   -c model_provider="minimax" >   -c 'model_providers.minimax={name="MiniMax",base_url="https://api.minimax.chat/v1",
>        env_key="MINIMAX_API_KEY",wire_api="responses"}' >   -m MiniMax-M3 --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox >   "pip install 一直 timeout，帮我看看是什么原因？"
> ```
>
> → the JSONL event stream contains `server=misakanet tool=misakanet_search` with
> `{"query":"pip install timeout","detail":"summary","top":5}`, and the returned results carry
> the lesson text. So the chain works end to end: config → prompt instructions → tool call →
> answer. Two notes for anyone re-running it: Codex 0.154.0 **rejects `wire_api = "chat"`**
> (Responses API only — MiniMax serves `/v1/responses`, so `"responses"` is the working value),
> and `--json` is what makes the tool call visible (plain `exec` output does not name it).
| DeepSeek Harness | MCP adapter | ✅ Supported |
| Gemini CLI | MCP | ✅ Supported |
| Windsurf | MCP | ✅ Supported |
| OpenCode | MCP | ✅ Supported |
| Copilot | MCP | ✅ Supported |

## Other

| Integration | Status | Notes |
|---|---|---|
| Smithery | ⏸ Paused | Pending upstream changes |

## Field reports

- [Agent integration matrix — 2026-09-15/16](agent-integration-matrix-2026-09-16.md) — one row per
  agent (Claude Code, hermes, openclaw, codex, codewhale, DSH), the command that produced the
  evidence, and what each agent actually did with MisakaNet. Re-run the commands in it rather than
  trusting this table.
