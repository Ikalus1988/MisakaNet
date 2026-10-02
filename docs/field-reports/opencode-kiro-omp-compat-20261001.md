# Field Report: OpenCode / Kiro / Oh-my-Pi Compatibility Documentation

- **Date:** 2026-10-01
- **Environment:** macOS Darwin 25.5.0 / Python 3.x
- **Related Issue:** #1947

---

## 1. Scope

Document MCP configuration for three clients: OpenCode, Kiro, Oh-my-Pi (OMP).
All three clients support MCP over HTTP — MisakaNet's remote endpoint (`https://misakanet.org/mcp`) should work with each.

## 2. Local Verification

### OpenCode

| Item | Status | Evidence |
|---|---|---|
| CLI installed | ❌ Not installed | `which opencode` → not found |
| Config file exists | ✅ Verified | `~/.config/opencode/opencode.json` exists on this machine |
| Config contains MCP | ✅ Verified | `feishu-mcp-pro` entry present with `type: "local"`, `command: [...]` |
| MCP key name | ✅ Verified from config | Key is `mcp` (not `mcpServers`) |
| URL field name | ⚠️ Inferred from docs | `url` with `type: "remote"` (existing config uses `type: "local"` + `command`) |
| MisakaNet added | ❌ Not yet | Config has only `feishu-mcp-pro`; MisakaNet entry not added (no CLI to test) |

**OpenCode config structure observed:**
```json
{
  "mcp": {
    "feishu-mcp-pro": {
      "type": "local",
      "command": ["npx", "-y", "..."],
      "enabled": true
    }
  }
}
```

### Kiro

| Item | Status | Evidence |
|---|---|---|
| CLI installed | ❌ Not installed | `which kiro` → not found |
| Config file exists | ❌ No config found | `~/.kiro/settings/mcp.json` does not exist |
| Config key name | ⚠️ From Kiro docs | `mcpServers` (same as Claude Code) |
| URL field name | ⚠️ From Kiro docs | `url` for remote endpoints |

### Oh-my-Pi (OMP)

| Item | Status | Evidence |
|---|---|---|
| CLI installed | ❌ Not installed | `which omp` → not found |
| Config file exists | ❌ No config found | `~/.omp/agent/mcp.json` does not exist |
| Config key name | ⚠️ From OMP docs | Flat layout — no `mcpServers` wrapper |
| URL field name | ⚠️ From OMP docs | `url` with `type: "http"` |

## 3. Integration Docs Created

| File | Client | Config Key | URL Field | Type Field |
|---|---|---|---|---|
| [opencode.md](../integrations/opencode.md) | OpenCode | `mcp` | `url` | `type: "remote"` |
| [kiro.md](../integrations/kiro.md) | Kiro | `mcpServers` | `url` | (inferred from URL) |
| [oh-my-pi.md](../integrations/oh-my-pi.md) | OMP | flat per-server | `url` | `type: "http"` |

## 4. What Requires Runtime Verification

All three docs are written from public documentation and local config inspection.
The following need runtime verification when the CLIs become available:

1. **OpenCode remote MCP**: Does `type: "remote"` + `url` actually connect to `https://misakanet.org/mcp`?
2. **Kiro MCP transport**: Does Kiro auto-detect Streamable HTTP from the `url` field, or does it need `type`?
3. **OMP headers support**: Does OMP's `mcp.json` support `headers` for Bearer token auth?
4. **Tool visibility**: Do all 7 MisakaNet MCP tools appear in each client's tool list?
5. **Live search**: Does `misakanet_search` return results from each client? *(unverified — no CLI installed to run the call)*

## 5. Diff from Issue Requirements

The issue asks for:
- ✅ `docs/integrations/opencode.md` — created
- ✅ `docs/integrations/kiro.md` — created
- ✅ `docs/integrations/oh-my-pi.md` — created
- ✅ `docs/field-reports/opencode-kiro-omp-compat-20261001.md` — this file
- ⚠️ Runtime smoke test — not possible (CLIs not installed); documented what needs verification

## 6. Recommendation

The three integration docs are ready to merge. They document the config format for each client based on public documentation and local config inspection. A follow-up PR with runtime smoke test evidence can be submitted once the CLIs are installed.

The `README.md` in `docs/integrations/` has been updated to add these three clients to the "Available Integrations" table (done in this PR).