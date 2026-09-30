# GitHub Copilot

GitHub Copilot is **one name, three incompatible MCP config shapes**. Copy the
wrong recipe into the wrong surface and the server silently fails to
register — there is no error, it just never appears in the tool list.

| Surface | Top-level key | Config location |
|---|---|---|
| VS Code (Copilot Chat) | **`servers`** (not `mcpServers`) | `.vscode/mcp.json` (workspace) or the user profile `mcp.json` |
| Copilot CLI | `mcpServers` | `~/.copilot/mcp-config.json`, or project `.mcp.json` / `.github/mcp.json` |
| github.com coding agent | `mcpServers` | Pasted into repo **Settings → Copilot → Coding agent → MCP configuration** (no file in the repo) |

Pick the section for the surface you're configuring and copy the snippet
as-is — do not mix keys between surfaces.

## VS Code (Copilot Chat)

VS Code uses `servers`, **not** `mcpServers`. Pasting a `mcpServers` block
here is the classic trap: VS Code accepts the file, shows no error, and the
server just never shows up in the Copilot Chat tools list.

Workspace config: `.vscode/mcp.json`

```json
{
  "servers": {
    "misakanet": {
      "command": "python",
      "args": ["-m", "misakanet.mcp_server"]
    }
  }
}
```

The same shape also works in the user profile's `mcp.json` (via
**Preferences: Open User MCP Configuration** in the Command Palette) if you
want MisakaNet available in every workspace.

## Copilot CLI

Copilot CLI uses `mcpServers`, matching the common MCP convention used by
Claude Desktop/Code, Cursor, etc.

Global config: `~/.copilot/mcp-config.json`
Project config: `.mcp.json` or `.github/mcp.json`

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

## github.com coding agent

The coding agent has no config file in the repository. Instead, paste an
`mcpServers` block into **Settings → Copilot → Coding agent → MCP
configuration** for the repository.

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

## Troubleshooting

- **Server doesn't appear in VS Code Copilot Chat**: check that the config
  uses `servers`, not `mcpServers`. VS Code does not warn on an unrecognized
  `mcpServers` key — the file is simply treated as having no servers.
- **Works in Copilot CLI but not VS Code (or vice versa)**: the two surfaces
  read different files with different top-level keys; a config valid for one
  is not automatically valid for the other. Keep separate files per surface
  rather than trying to share one.
