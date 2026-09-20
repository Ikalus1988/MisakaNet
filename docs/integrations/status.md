# Integration Status

> Last updated: 2026-09-20

Two different questions hide behind "do you support X?", so this page answers them separately:

- **Does the installer wire it for you?** `npx @misaka-net/misakanet-setup` writes five agents'
  configs and can re-check them (`--verify`). Everything else is a manual recipe.
- **Can it talk to us at all?** The endpoint is standard MCP over Streamable HTTP, so a client that
  supports MCP usually needs one config entry. That is per-vendor knowledge, and it is where the
  mistakes happen: the config *key* differs between products (`mcpServers`, `servers`, `mcp`,
  `mcp_servers`, `mcp.servers`) and so does the field that holds the URL (`url`, `httpUrl`,
  `serverUrl`).

**Evidence levels used below** — the useful distinction is who checked it, and how:

| Mark | Meaning |
|---|---|
| ✅ **verified** | A command and its output are recorded in this repository (the installer's `--verify`, or the [field-report matrix](../field-reports/agent-integration-matrix-2026-09-16.md)). Re-run the command rather than trusting this page |
| 🟡 **recipe** | Steps are documented here, but no run is recorded — treat as "we believe this works" |
| 🔵 **vendor-only** | The vendor's own docs say it works (checked 2026-09-20, links below). Nothing in this repository documents or tests it |
| ⚪ **no coverage** | Nobody has looked |

## MCP Registries

| Registry | Status | URL |
|---|---|---|
| Glama | ✅ Listed, MCP indexed | https://glama.ai/mcp/servers/Ikalus1988/MisakaNet |
| MCP Registry | ✅ Listed | https://modelcontextprotocol.io |
| MCP Toplist | ✅ Badge live | https://mcptoplist.com/server/io.github.Ikalus1988%2Fmisakanet |

## Agents

| Agent | Installer writes it | Docs here | MCP + remote HTTP endpoint | Evidence |
|---|---|---|---|---|
| **Claude Code** | ✅ `~/.claude.json`, `~/.claude/CLAUDE.md`, hooks + read-only tool grants in `~/.claude/settings.json` | [claude-code.md](claude-code.md), [playbook](claude-code-failure-memory.md) | yes, native http | ✅ verified (installer + field report: 7 tools, called, lesson quoted back) |
| **Codex** | ✅ `~/.codex/config.toml` (`mcp_servers`), `~/.codex/AGENTS.md` | field report §2.4 | yes, `streamable-http` | ✅ verified (live session: config → prompt → tool call → answer) |
| **Hermes Agent** (Nous Research) | ✅ `~/.hermes/config.yaml` (`mcp_servers`), `~/.hermes/.env`, `~/.hermes/SOUL.md` | field report only | yes: `url`, Streamable HTTP by default | ✅ verified (7 tools registered; the one `no_match` was a corpus bug we then fixed) |
| **OpenClaw** | ✅ `~/.openclaw/openclaw.json` (`mcp.servers`), `~/.openclaw/workspace/AGENTS.md` | field report only | yes: `transport: "streamable-http"` \| `"sse"` | ✅ verified (`toolSummary: {calls: 3, failures: 0}`) |
| **Codewhale** | ✅ `~/.codewhale/mcp.json` | field report only | yes: Streamable HTTP, legacy SSE fallback | ✅ verified (`codewhale mcp tools` → 7; search → get_lesson) |
| **DeepSeek Harness** | via the plugin channel, not the installer | [dsh.md](dsh.md) | yes (plugin bundle) | ✅ verified (`dsh --dump-config`, install) |
| **Cursor** | ❌ | [cursor.md](cursor.md), [failure-memory rule](cursor-failure-memory.md) | yes since 0.45: `~/.cursor/mcp.json` + `.cursor/mcp.json` | 🟡 recipe (docs teach the clone + stdio path; the remote URL path is shorter) |
| **Continue.dev** | ❌ | [continue.md](continue.md) | per vendor docs | 🟡 recipe |
| **Gemini CLI** | ❌ | — (this page only) | yes: `~/.gemini/settings.json`, remote field **`httpUrl`** | 🔵 vendor-only ([mcp-server](https://geminicli.com/docs/tools/mcp-server/)) |
| **Windsurf** | ❌ | — | yes, **but read the caveat**: `~/.codeium/windsurf/mcp_config.json` applies to the legacy Cascade agent; the current docs moved to `docs.devin.ai` ([MCP](https://docs.devin.ai/desktop/cascade/mcp)) | 🔵 vendor-only, and partly stale |
| **GitHub Copilot** | ❌ | — | yes, in **three shapes**: VS Code uses **`servers`** in `.vscode/mcp.json` / profile `mcp.json` ([ref](https://code.visualstudio.com/docs/copilot/reference/mcp-configuration)); Copilot CLI uses `mcpServers` in `~/.copilot/mcp-config.json`; the github.com coding agent is configured in repo Settings, no file | 🔵 vendor-only |
| **OpenCode** | ❌ | — | yes: `~/.config/opencode/opencode.json`, key **`mcp.<name>`** with `type: "remote"` ([docs](https://opencode.ai/docs/mcp-servers/)) | 🔵 vendor-only |
| **Kiro** (AWS) | ❌ | — | yes since launch (2025-07-14): `~/.kiro/settings/mcp.json` (`mcpServers`), project `.kiro/settings/mcp.json` ([docs](https://kiro.dev/docs/mcp/configuration/)) | 🔵 vendor-only |
| **Trae** (ByteDance; docs now call it TraeCode) | ❌ | — | yes since v1.3.1 (2025-04-22), **project scope only**: `.trae/mcp.json` (`mcpServers`), gated by "Enable Project MCP". No user/global path is documented ([docs](https://docs.trae.ai/ide/add-mcp-servers)) | 🔵 vendor-only |
| **Google Antigravity** | ❌ | — | yes, one central file shared by the app, IDE and CLI: `~/.gemini/config/mcp_config.json`, key `mcpServers` with **`serverUrl`** ([codelab](https://codelabs.developers.google.com/google-workspace-mcp-antigravity)) | 🔵 vendor-only, incomplete: headers, project scope, rules file and hooks are *not found* in reachable Google sources, not confirmed absent |
| **Oh-my-Pi** (`omp`) | ❌ | — | yes: project `.omp/mcp.json`, user `~/.omp/agent/mcp.json`, `type: "http"` ([docs](https://github.com/can1357/oh-my-pi/blob/main/docs/mcp-config.md)) | 🔵 vendor-only |
| **Pi** | ❌ | — | **no native MCP** — the client is rules-only unless you add the third-party `pi-mcp-adapter`. Pi reads `AGENTS.md`/`CLAUDE.md`, so the [failure-memory playbook](claude-code-failure-memory.md) is the usable path | 🔵 vendor-only (absence of a documented MCP entry point) |
| **Aider / Cline / Zed** | ❌ | — | not checked this round; the old "Planned" rows here overstated nothing but promised nothing either | ⚪ no coverage |

> **The key-name trap, in one place.** `mcpServers` (Claude Code, Cursor, Gemini CLI, Windsurf,
> Kiro, Trae, Copilot CLI) · `servers` (**VS Code Copilot**) · `mcp` (OpenCode) · `mcp_servers`
> (Codex TOML, Hermes YAML) · `mcp.servers` (OpenClaw). For the URL field: `url` is most common,
> Gemini CLI also accepts `httpUrl`, Antigravity requires `serverUrl`. A config entry copied from
> one product into another usually fails **silently** — the server simply never appears.

> **Names that collide.** `oh-my-pi` on npm is *not* the 32k-star agent (that is
> `@oh-my-pi/pi-coding-agent`); "Hermes Agent" is Nous Research's agent, a different product from
> their Hermes LLMs; `codewhale` is `Hmbown/Codewhale` (the `CodeWhaleIDE` repos are unrelated);
> Trae's IDE docs are now headed "TraeCode" while TraeWork is a separate product, and the CN build
> keeps rules under `~/.trae-cn/`.

## Codex: what "verified" means here

Codex is the one row with a full chain recorded, so it doubles as the template for the others
(codex-cli 0.154.0, 2026-09-15 — re-run these, don't take the table's word for it):

```bash
codex mcp list              # → misakanet | https://misakanet.org/mcp | enabled | Bearer token
codex doctor                # → config.toml parse ok · MCP servers 1 · 1 streamable_http · 0 disabled
codex debug prompt-input "" # → a `# AGENTS.md instructions` item carrying the rule block
```

The third one is the interesting one: it renders what the model will actually see, so it proves the
user-level `~/.codex/AGENTS.md` block reaches the prompt rather than merely existing on disk. Codex
has no user-level lifecycle hook (0.154.0 hooks are admin-managed through `requirements.toml`), so
the round-20 checkpoint reminder is rule-driven there, not hook-driven.

**A live session calls the tool** (2026-09-15, codex-cli 0.154.0 driven by MiniMax-M3):

```bash
MINIMAX_API_KEY=… codex exec --json \
  -c model_provider="minimax" \
  -c 'model_providers.minimax={name="MiniMax",base_url="https://api.minimax.chat/v1",
       env_key="MINIMAX_API_KEY",wire_api="responses"}' \
  -m MiniMax-M3 --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox \
  "pip install 一直 timeout，帮我看看是什么原因？"
```

→ the JSONL event stream contains `server=misakanet tool=misakanet_search` with
`{"query":"pip install timeout","detail":"summary","top":5}`, and the returned results carry the
lesson text. The chain works end to end: config → prompt instructions → tool call → answer. Two notes
for anyone re-running it: Codex 0.154.0 **rejects `wire_api = "chat"`** (Responses API only — MiniMax
serves `/v1/responses`, so `"responses"` is the working value), and `--json` is what makes the tool
call visible (plain `exec` output does not name it).

## Other

| Integration | Status | Notes |
|---|---|---|
| Smithery | ⏸ Paused | Pending upstream changes |
| Any other MCP client | ✅ unverified but standard | `https://misakanet.org/mcp` speaks Streamable HTTP and answers `tools/list` with 7 tools; reads are anonymous and unmetered. If your client needs a bridge (`mcp-remote`, `supergateway`), say so in [#1550](https://github.com/Ikalus1988/MisakaNet/issues/1550) and we will document it |

## Field reports

- [Agent integration matrix — 2026-09-15/16](../field-reports/agent-integration-matrix-2026-09-16.md) — one row per
  agent (Claude Code, hermes, openclaw, codex, codewhale, DSH), the command that produced the
  evidence, and what each agent actually did with MisakaNet. Re-run the commands in it rather than
  trusting this table.
