---
title: "Codex desktop: reload MCP config without restarting the app"
domain: development
tags: [codex, mcp, config, reload, desktop, stdio]
status: published
evidence_level: E3
summary_plain: "Codex 桌面版的 MCP 配置改了之后不会自动生效，需要重启 app-server 进程才能加载新配置。"
trigger: "codex mcp remove desktop config reload stdio app-server"
verify: "codex mcp list 后修改配置，重启 app-server，再次 codex mcp list 确认变更生效"
provenance: verified
---

## Problem

After running `codex mcp remove <server>` to remove an MCP server registration,
the already-running Codex desktop app-server continues to spawn the removed server.
The TOML config file is updated (verified via `codex mcp get`), but the running
process does not re-read it. There is no named control socket or reload signal for
the desktop app-server's stdio-based MCP transport.

## Root Cause

The Codex desktop app-server reads MCP configuration at startup and caches it for
the lifetime of the process. `codex mcp remove` writes the TOML file but does not
signal the running app-server. The stdio transport has no reload mechanism — unlike
HTTP-based servers, there is no endpoint to POST a reload command to.

## Solution

Restart the app-server process after modifying MCP configuration:

```bash
# 1. Remove the MCP server
codex mcp remove <server-name>

# 2. Verify the config file is updated
codex mcp get <server-name>
# Expected: error or empty — server no longer in config

# 3. Restart the Codex desktop app
# macOS: Cmd+Q the app, then reopen
# Or kill the app-server process:
pkill -f "codex.*app-server"

# 4. Verify the running instance no longer spawns the removed server
codex mcp list
# Expected: removed server is absent
```

For CLI-only usage (no desktop app), changes take effect on the next `codex` invocation
since the CLI reads config fresh each time.

## Verification

```bash
# List current MCP servers
codex mcp list 2>/dev/null | head -5
# Note the servers listed

# Remove one (if any exist)
# codex mcp remove <name>

# Restart and verify
pkill -f "codex.*app-server" 2>/dev/null || true
sleep 2
codex mcp list 2>/dev/null | head -5
# Expected: removed server no longer appears
```
