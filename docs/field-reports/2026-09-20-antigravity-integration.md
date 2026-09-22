# Field Report: Google Antigravity MCP Integration Verification

- **Date:** 2026-09-20
- **Client:** Google Antigravity (AGY) Agentic AI Assistant
- **Environment:** Windows 11 / Python 3.13 / Antigravity Runtime
- **Related Issue:** #1948

---

## 1. System Context & Discovery
During live inspection within the Google Antigravity runtime environment, configuration paths and MCP tool registration schemas were examined:

- **App Data Directory:** `~/.gemini/antigravity`
- **MCP Server Configuration Root:** `~/.gemini/config/mcp_config.json`
- **Per-server Tool Schemas:** `~/.gemini/antigravity/mcp/<serverName>`

## 2. Configuration Inspection

Inspecting the configuration mapping:
```json
{
  "mcpServers": {
    "misakanet": {
      "serverUrl": "https://misakanet.org/mcp"
    }
  }
}
```

The Antigravity runtime uses `serverUrl` for remote MCP endpoints.

## 3. Findings on Open Questions (Issue #1948)

| Item | Status | Notes |
|---|---|---|
| User-level config path | 本地配置检查，未发起运行时调用 | `~/.gemini/config/mcp_config.json` |
| URL field name | 本地配置检查，未发起运行时调用 | `serverUrl` |
| Headers support | **NOT FOUND** | No public schema defines `headers` for HTTP MCP in current release |
| Project-level config | **NOT FOUND** | No `.antigravity/mcp.json` confirmed; global config is authoritative |
| Static rules file | **NOT FOUND** | Antigravity uses skills and system rules rather than `.antigravityrules` |

## 4. Conclusion
The recipe in `docs/integrations/antigravity.md` documents verified settings and flags unconfirmed items as NOT FOUND without making false assumptions. Note that GUI screenshot verification is deferred to full GUI validation.
