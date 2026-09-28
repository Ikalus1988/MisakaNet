# Google Antigravity Integration Recipe

This document provides the configuration recipe and integration details for connecting MisakaNet's MCP service with **Google Antigravity (AGY)**.

## Overview & Scope

Google Antigravity is Google DeepMind's agentic AI coding environment. It supports MCP (Model Context Protocol) tool integrations both eagerly loaded and lazily loaded.

> **Status Grade Recommendation:** 🔵 **vendor-only** (or 🟡 **recipe** for the central JSON structure)  
> *Reasoning:* While the global user-level config path (`~/.gemini/config/mcp_config.json`) and the `serverUrl` field are confirmed in the client runtime environment, remote custom headers, project-level configuration scopes, and workspace static rules files remain unconfirmed in public schemas and are explicitly marked as **NOT FOUND**. Per the MisakaNet grading criteria, this entry should remain 🔵 vendor-only until end-to-end verification is established.


---

## Configuration Recipe

### Configuration Path
- **Global User Config**: `~/.gemini/config/mcp_config.json` (or on Windows: `%USERPROFILE%\.gemini\config\mcp_config.json`)
- **App Data Directory**: `~/.gemini/antigravity/mcp/` (contains per-server tool directories and schemas)

### Known Configuration Structure

In Google Antigravity, MCP servers can be configured in `~/.gemini/config/mcp_config.json` under the `mcpServers` key:

```json
{
  "mcpServers": {
    "misakanet": {
      "serverUrl": "https://misakanet.org/mcp"
    }
  }
}
```

Alternatively, for local subprocess-based MCP execution:
```json
{
  "mcpServers": {
    "misakanet": {
      "command": "python",
      "args": ["-m", "misakanet.mcp_server"]
    }
  }
}
```

---

## Knowns vs. Uncertainties

To maintain documentation integrity, verified features and unverified items are explicitly separated below:

### Known & Verified
1. **Central Config File**: `~/.gemini/config/mcp_config.json` is read by the Antigravity runtime for external MCP server registrations.
2. **Key Name**: `mcpServers` is the root mapping key.
3. **URL Field**: For HTTP/SSE streaming remote MCP servers, the connection URL field is `serverUrl`.
4. **Tool Discovery**: Antigravity registers eager tools directly into the agent's context and lazy tools with deferred parameter schemas.

### Uncertainties & NOT FOUND
*(Items below are explicitly marked **NOT FOUND (does not imply unsupported)**)*
1. **Custom HTTP Headers**:
   - `headers` object inside `mcpServers.<name>`: **NOT FOUND** in reachable Google Antigravity public documentation. (If token authentication is required, it must be verified whether `headers` or query parameters are accepted).
2. **Project-level Configuration**:
   - `.antigravity/mcp.json` or `.gemini/mcp.json` in project root: **NOT FOUND** in official public schemas (global config in `~/.gemini/` is currently the canonical discovery path).
3. **Rules Files & Custom Hooks**:
   - Equivalent to `CLAUDE.md` or `.cursorrules`: Antigravity uses system prompt customization and built-in agent skill instructions (`SKILL.md`), but a standalone static `.antigravityrules` file in the workspace root is **NOT FOUND**.

---

## Verification & Usage

In Google Antigravity sessions:
- Tools exposed by `misakanet` (e.g. `misakanet_search`, `misakanet_get_lesson`) can be called natively by the agent or invoked through standard MCP tool calling protocols.
- Refer to [docs/field-reports/2026-09-20-antigravity-integration.md](../field-reports/2026-09-20-antigravity-integration.md) for local configuration review and empirical findings.

