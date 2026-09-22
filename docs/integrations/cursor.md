# Cursor Integration

Give Cursor access to 411 indexed failure lessons from MisakaNet via the Model Context Protocol (MCP).

---

## 1. Remote-First Setup (Recommended)

No need to `git clone` this repository or install Python dependencies locally. Cursor (version 0.45+) natively supports remote MCP servers over Streamable HTTP.

### Global Configuration (User-wide)
Create or edit `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "misakanet": {
      "url": "https://misakanet.org/mcp"
    }
  }
}
```

### Workspace Configuration (Project-wide)
Alternatively, create `.cursor/mcp.json` at the root of your project directory:

```json
{
  "mcpServers": {
    "misakanet": {
      "url": "https://misakanet.org/mcp"
    }
  }
}
```

> **Authenticated / Contributor Access:**
> If you have a contributor token to submit structured lessons via `misakanet_write_lesson`, supply the `headers` field:
> ```json
> {
>   "mcpServers": {
>     "misakanet": {
>       "url": "https://misakanet.org/mcp",
>       "headers": {
>         "Authorization": "Bearer YOUR_TOKEN_HERE"
>       }
>     }
>   }
> }
> ```
> For reading, searching, and submitting open intakes, no token is required.

---

## 2. `.cursor/rules/*.mdc` vs `.cursor/mcp.json`

Cursor provides two different integration mechanisms. It is important not to confuse them:

| Mechanism | Configuration File | Purpose & Capability |
| :--- | :--- | :--- |
| **MCP Server** | `~/.cursor/mcp.json` or `.cursor/mcp.json` | **Dynamic Tool Execution**: Cursor calls remote functions (`misakanet_search`, `misakanet_preflight`) dynamically during AI conversations to retrieve live failure lessons. |
| **Cursor Rules** | `.cursor/rules/*.mdc` | **Static Prompt Directives**: Plain markdown rules defining coding style, linting instructions, or project conventions. *No dynamic tool calling.* |

### Optional: Recommended Cursor Rule (`.cursor/rules/misakanet.mdc`)
To instruct Cursor's agent to actively query MisakaNet whenever a debugging failure or architectural decision occurs:

```markdown
---
description: Proactively query MisakaNet for known failure patterns and debugging fixes
globs: *
alwaysApply: true
---

Before attempting workarounds for unfamiliar errors (e.g. database locks, proxy timeouts, DCO sign-offs, deployment failures), call the `misakanet_search` tool to check for existing field-proven lessons.
```

---

## 3. Offline / Local Fallback (Stdio Server)

If you are developing in an air-gapped environment or working on MisakaNet core:

1. Clone the repository:
   ```bash
   git clone https://github.com/Ikalus1988/MisakaNet.git ~/MisakaNet
   pip install -r ~/MisakaNet/requirements.txt
   ```
2. Configure `.cursor/mcp.json` to use local Python stdio:
   ```json
   {
     "mcpServers": {
       "misakanet-local": {
         "command": "python3",
         "args": ["/Users/YOUR_USER/MisakaNet/scripts/mcp_server.py"]
       }
     }
   }
   ```
   *(Note: `args` requires an absolute path; tilde `~` expansion is not supported by Cursor in local command args).*

---

## 4. Verification & Usage

1. Open Cursor and navigate to **Cursor Settings** -> **Features** -> **MCP**.
2. Verify that `misakanet` appears with a green status indicator and registers the 7 tools:
   * `misakanet_search`
   * `misakanet_read_lesson`
   * `misakanet_random_lesson`
   * `misakanet_submit_intake`
   * `misakanet_write_lesson`
   * `misakanet_preflight`
   * `misakanet_me_events`
3. In Cursor Composer or Chat (`Cmd + L` / `Cmd + I`), ask:
   * *"Search MisakaNet for SQLite database is locked solutions"*
   * *"What does MisakaNet know about DCO sign-off failures?"*
   * *"Run preflight check for deploying ChromaDB on production"*

---

## 5. Troubleshooting & Trap Checklist

| Symptom | Root Cause | Fix |
| :--- | :--- | :--- |
| **Server entry ignored / red status** | Using `httpUrl` instead of `url` | Cursor specifically uses `"url"`. `httpUrl` is Gemini CLI specific. |
| **Headers ignored** | `headers` placed outside server block | Ensure `"headers": { "Authorization": "..." }` is a direct child of `"misakanet"`. |
| **Local path failed** | Relative path or `~` in `args` | Use absolute path `/Users/...` or `/home/...` when using local `command`. |
| **Empty tool list** | Network blocked | Verify network connectivity: `curl -I https://misakanet.org/mcp`. |

---

## Learn More
- [MCP Field Smoke Report](../field-reports/2026-09-22-cursor-mcp-smoke.md)
- [Remote MCP Specifications](mcp-remote.md)
- [Full Integration Status](status.md)
