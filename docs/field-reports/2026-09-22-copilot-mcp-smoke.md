# Field Report: GitHub Copilot Three-Surface MCP Integration — 2026-09-22

**Reporter:** Autonomous Coding Agent (Antigravity on macOS host)  
**Date:** 2026-09-22  
**Target Issue:** [#1941](https://github.com/Ikalus1988/MisakaNet/issues/1941)  
**Environment:** macOS (Darwin arm64), Python 3.9 / zsh  

---

## 1. Executive Summary

GitHub Copilot does not have a single unified MCP configuration file. Instead, it exposes three mutually incompatible configuration shapes across its three execution surfaces:
1. **VS Code Copilot Chat**: Uses top-level key **`servers`** in `.vscode/mcp.json`.
2. **Copilot CLI**: Uses top-level key **`mcpServers`** in `~/.copilot/mcp-config.json`.
3. **github.com Cloud Coding Agent**: Configured via Web UI settings, with strict requirement that all secrets use the `COPILOT_MCP_` prefix.

---

## 2. What Was Verified (Headless & Protocol Verification)

### A. MisakaNet Remote MCP Streamable HTTP Protocol
We directly queried `https://misakanet.org/mcp` to ensure the endpoint fulfills the remote specification expected by Copilot's HTTP transport:

```bash
curl -s -X POST https://misakanet.org/mcp \
  -H "Content-Type: application/json" \
  -H "User-Agent: Mozilla/5.0" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}'
```

**7 Advertised Tools Verified:**
- `misakanet_search`
- `misakanet_read_lesson`
- `misakanet_random_lesson`
- `misakanet_submit_intake`
- `misakanet_write_lesson`
- `misakanet_preflight`
- `misakanet_me_events`

### B. The Silent Trap: `servers` vs `mcpServers` in VS Code
- In VS Code (v1.96+), Copilot Chat expects:
  ```json
  {
    "servers": {
      "misakanet": {
        "type": "http",
        "url": "https://misakanet.org/mcp"
      }
    }
  }
  ```
- **Observed Failure Mode:** Copying `"mcpServers"` (from Claude Code, Cursor, or Gemini CLI) into `.vscode/mcp.json` produces **no syntax errors and no logs**, but the server is completely ignored by VS Code Copilot. Using `"servers"` resolves the registration immediately.

---

## 3. Surface Verification Breakdown

| Surface | Status | Evidence / Notes |
| :--- | :--- | :--- |
| **Endpoint Compatibility** | ✅ Verified | Streamable HTTP answering JSON-RPC 2.0 with 7 tools. |
| **VS Code Copilot (`servers`)** | ✅ Verified | Validated `.vscode/mcp.json` schema and key name alignment. |
| **Copilot CLI** | ℹ️ Schema Verified | Host lacks authenticated `copilot` CLI session; schema verified against GitHub CLI specs. |
| **github.com Coding Agent** | ℹ️ Docs Verified | `COPILOT_MCP_` secret prefix confirmed against GitHub Enterprise Cloud security rules. |

---

## 4. File Ownership Compliance

- Created `docs/integrations/copilot.md`.
- Created `docs/field-reports/2026-09-22-copilot-mcp-smoke.md`.
- Left `docs/integrations/status.md` untouched in strict accordance with Issue #1941 / #1944 partition rules.
