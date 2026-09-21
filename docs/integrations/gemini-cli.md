# Gemini CLI Integration

Connect Google Gemini CLI to MisakaNet's failure memory knowledge base via native Streamable HTTP remote MCP.

Reads are anonymous, open, and unmetered.

## Overview & Official References

Google Gemini CLI natively supports Model Context Protocol (MCP) using Streamable HTTP.
Configuration is stored in user global settings `~/.gemini/settings.json` (or workspace-level `.gemini/settings.json`).

> **Official Gemini CLI MCP Documentation**:
> - [Gemini CLI MCP Specification & Configuration Guide](https://ai.google.dev/gemini-api/docs/mcp)
> - [Model Context Protocol Specification](https://modelcontextprotocol.io)

---

## Configuration Shape: `httpUrl` & `headers`

Unlike clients that expect `url`, Gemini CLI uses **`httpUrl`** for remote Streamable HTTP servers:

```json
{
  "mcpServers": {
    "misakanet": {
      "httpUrl": "https://misakanet.com/mcp",
      "headers": {
        "User-Agent": "MisakaNet-GeminiCLI/1.0",
        "Accept": "application/json, text/event-stream"
      }
    }
  }
}
```

---

## Rules & Context File Hierarchy (`GEMINI.md`)

Gemini CLI reads contextual guidelines from `GEMINI.md` following a standard inheritance cascade:

1. **User Global Layer**: `~/.gemini/GEMINI.md` (applies across all terminal sessions)
2. **Project Workspace Layer**: `<workspace-root>/GEMINI.md` (overrides/augments global rules for the repository)
3. **Subdirectory Context Layer**: `<workspace-root>/<subdir>/GEMINI.md` (scoped instructions when executing inside subpackages)

### Pre-Retry Search Hook Note
- **Hooks Configuration**: In pure headless CLI mode, automatic failure interception (e.g. executing `misakanet_search` immediately upon test failure before retry) is **currently unverified in pure CLI**.
- **Recommended Practice**: Explicitly include standard guidance in `GEMINI.md`:
  ```markdown
  Before retrying any failed command or build error, invoke the `misakanet_search` tool with the exact error signature to retrieve proven solutions.
  ```

---

## Modes

### Mode A. Manual MCP Config (Direct)
Edit `~/.gemini/settings.json` and append the `misakanet` entry under `mcpServers`.

### Mode B. Project-Scoped Config
Add `.gemini/settings.json` directly inside your workspace root.
