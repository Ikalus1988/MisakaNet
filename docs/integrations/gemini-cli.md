# Gemini CLI Integration

Give Gemini CLI access to 402 indexed failure lessons from MisakaNet.

Gemini CLI natively supports Streamable HTTP MCP. The config key is **`mcpServers`**,
and the remote URL field is **`httpUrl`** (not `url`) — that distinction is the common
copy-paste trap, since most other clients use `url`.

## Setup

Create or edit `~/.gemini/settings.json` (user scope) or project `.gemini/settings.json`:

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

Notes:

- `httpUrl` is the Gemini CLI-specific key for remote MCP endpoints; `url` also works in
  some versions but `httpUrl` is what the official docs advertise.
- `headers` is optional. Without a Bearer token you get anonymous, unmetered reads (the
  `tools/list` → `tools/call` flow still works). Add a token only if you need the write tools.
- No clone, no local server, no Python dependency. Gemini CLI talks to the remote endpoint
  directly over Streamable HTTP.

Official reference: [Gemini CLI MCP server docs](https://geminicli.com/docs/tools/mcp-server/).

## Usage

In a Gemini CLI session, ask something that should hit the tool, e.g.:

- "Search MisakaNet for DCO sign-off failure"
- "Find lessons about pip install timeout"
- "What does MisakaNet know about GitHub token issues"

Gemini CLI should call `misakanet_search` under the hood and return matching lessons.

## Demo Queries

| Query | What you'd expect |
|-------|-------------------|
| DCO sign-off failed | Fix workflow with `--amend --signoff` |
| pip install timeout | SSL/proxy timeout solutions |
| GitHub token exposed | Secret scanning response pattern |
| database locked | SQLite WAL mode + timeout fix |

## GEMINI.md Hierarchy

Gemini CLI reads project-level `GEMINI.md` (and any subdirectory `GEMINI.md` files) as
instructions that the model sees alongside the user prompt. The MisakaNet rules block can
live in those files, but this integration is MCP-only: the tool call is what surfaces
lesson content, not a rules-file echo. If you also want the rule-driven "retry before
search" pattern, that lives in the failure-memory playbook for Claude Code; Gemini CLI
hooks are not confirmed to expose a comparable checkpoint hook in the reachable docs.

## Hooks

As of the docs checked 2026-09-20, Gemini CLI hook support is not clearly documented in
reachable sources. If a "retry-before-search" hook exists, this page should be updated.
Until then: **hooks not verified**.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "No MCP server found" | Confirm `httpUrl` (not `url`) is the key; check `~/.gemini/settings.json` is valid JSON |
| Server appears but no tools | `gemini` may need a restart after editing settings; re-run `gemini mcp list` if available |
| Authorization errors | Remove the `Authorization` header for anonymous reads; the endpoint allows unmetered anonymous `tools/list` and `tools/call` |

## Learn More

- [MCP Quickstart](../mcp-quickstart.md)
- [Full MCP docs](../mcp.md)
- [Integration status matrix](status.md)
