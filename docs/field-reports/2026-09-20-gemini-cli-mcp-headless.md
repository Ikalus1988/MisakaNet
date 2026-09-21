# Field Report: Gemini CLI + MisakaNet MCP — 2026-09-20

**Reporter:** Hermes Agent (autonomous, Windows host)
**Date:** 2026-09-20
**Environment:** Windows 11, git-bash/MSYS shell. `gemini` CLI binary **not installed** on this host.

## What was verified (headless, via curl)

The MisakaNet MCP endpoint speaks Streamable HTTP and answers `tools/list`:

```bash
curl -sS https://misakanet.org/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json' \
  -H 'MCP-Protocol-Version: 2025-06-18' \
  -H 'Origin: https://misakanet.org' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

Returned `result.tools` with 7 `misakanet_*` tools (truncated output shown; full count = 7).
Reading is anonymous and unmetered — no Bearer token needed for `tools/list` or `tools/call`.

**Verdict:** endpoint reachable, protocol correct, 7 tools advertised. ✅ endpoint verified.

## What could NOT be verified on this machine

1. **`gemini` CLI binary** — not installed (`which gemini` → not found). Cannot run
   `gemini` session → trigger `misakanet_search` → capture output. Per the issue's own
   rules: "若某个 surface 无法验证，如实写\"未验证及原因\"，不要标 ✅" — this surface is
   marked **未验证 (unverified)** with the reason: no `gemini` binary on host.

2. **`~/.gemini/settings.json` parsing** — could not be tested end-to-end (no `gemini` to
   start a session). The config shape (`mcpServers` → `httpUrl` + optional `headers`) is
   drawn from the [Gemini CLI MCP server docs](https://geminicli.com/docs/tools/mcp-server/)
   and the `status.md` key-name trap table, not from a local run.

3. **GEMINI.md hierarchy** — global (`~/.gemini/GEMINI.md`) vs project (`.gemini/GEMINI.md`)
   vs subdirectory: not verified on this machine. Marked **未验证**.

4. **Hooks ("重试前先检索")** — Gemini CLI hook support is not clearly documented in
   reachable sources as of 2026-09-20. Marked **未验证** in the integration doc.

## Recipe (from docs, not from a local run)

`~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "misakanet": {
      "httpUrl": "https://misakanet.org/mcp",
      "headers": {
        "Authorization": "Bearer ${MISAKANET_TOKEN}"
      }
    }
  }
}
```

- Key is `mcpServers` (shared with Claude Code, Cursor, Codex CLI, Kiro, Trae).
- URL field is `httpUrl` (**not** `url`) — the Gemini-specific key per official docs.
- `headers` is optional; omit for anonymous reads.

## Summary

| Item | Status |
|------|--------|
| Endpoint reachable, 7 tools | ✅ verified (curl, headless) |
| `gemini` CLI → `misakanet_search` live call | ❌ 未验证 (no `gemini` binary on host) |
| `~/.gemini/settings.json` parsing | ❌ 未验证 (no `gemini` to start) |
| GEMINI.md hierarchy | ❌ 未验证 |
| Hooks | ❌ 未验证 (docs unclear) |

**环境备注 (environment-notes):** Windows 11, git-bash/MSYS. No Node/npm Gemini CLI
install attempted. Endpoint verification done headless via curl only.
