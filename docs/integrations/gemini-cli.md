# Gemini CLI – Remote MCP (httpUrl) Integration

## Overview

The **Gemini CLI** ships with native support for *Streamable HTTP* MCP servers.  
Unlike many other clients, the configuration key for a remote MCP is **`httpUrl`** (not `url`) and it also accepts custom `headers`.

Official documentation: <https://github.com/gemini-cli/gemini-cli#remote-mcp-httpurl>

---

## 1️⃣ Settings snippet

Place the following JSON fragment in **`~/.gemini/settings.json`** (or a project‑local `.gemini/settings.json`).  
Replace the placeholder values with those supplied by your MCP provider.

