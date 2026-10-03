# GitHub Copilot Integration

Give GitHub Copilot access to MisakaNet's indexed failure lessons.

GitHub Copilot supports MCP across **three incompatible configuration surfaces**. Each uses a different key name and file location — mixing them up causes silent failure (no error, server just doesn't appear).

## Surface 1: VS Code Copilot Chat

**Config key:** `servers` (NOT `mcpServers`)
**File:** `.vscode/mcp.json` (project) or user profile `mcp.json`

> ⚠️ Using `mcpServers` here silently fails — the server won't appear with no error message.

### Remote (recommended)

```json
{
  "servers": {
    "misakanet": {
      "type": "sse",
      "url": "https://api.misakanet.com/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_TOKEN"
      }
    }
  }
}
```

**Source:** [VS Code MCP configuration docs](https://code.visualstudio.com/docs/copilot/reference/mcp-configuration)

### Local

```json
{
  "servers": {
    "misakanet": {
      "command": "python3",
      "args": ["-m", "misakanet.server"],
      "cwd": "/path/to/MisakaNet"
    }
  }
}
```

**Verification status:** 🔵 Not verified (no VS Code available in test environment).

## Surface 2: Copilot CLI

**Config key:** `mcpServers`
**File:** `~/.copilot/mcp-config.json` (global) or `.mcp.json` / `.github/mcp.json` (project)

### Remote (recommended)

```json
{
  "mcpServers": {
    "misakanet": {
      "type": "sse",
      "url": "https://api.misakanet.com/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_TOKEN"
      }
    }
  }
}
```

### Local

```json
{
  "mcpServers": {
    "misakanet": {
      "command": "python3",
      "args": ["-m", "misakanet.server"],
      "cwd": "/path/to/MisakaNet"
    }
  }
}
```

**Verification status:** ✅ Verified — `copilot mcp list` shows the server and tools are discoverable.

**Source:** [GitHub Copilot CLI MCP docs](https://docs.github.com/en/copilot/using-github-copilot/using-copilot-coding-agent-in-the-cli)

## Surface 3: github.com Coding Agent

**Config key:** `mcpServers`
**Location:** Repository Settings → Code & automation → Copilot → Coding agent → MCP configuration
**No file** — configured through the GitHub web UI.

### Remote

```json
{
  "mcpServers": {
    "misakanet": {
      "type": "sse",
      "url": "https://api.misakanet.com/mcp",
      "headers": {
        "Authorization": "Bearer COPILOT_MCP_MISAKANET_TOKEN"
      }
    }
  }
}
```

### Required: Repository secrets/variables prefix

The `headers` values **must** reference repository secrets or variables with the `COPILOT_MCP_` prefix. The coding agent will not inject secrets without this prefix.

1. Go to repository **Settings → Secrets and variables → Actions**
2. Add a secret named `COPILOT_MCP_MISAKANET_TOKEN` with your MisakaNet token
3. Reference it in the config as `COPILOT_MCP_MISAKANET_TOKEN`

**Verification status:** 🔵 Not verified (requires GitHub Enterprise/Team with coding agent enabled).

**Source:** [GitHub Copilot coding agent MCP docs](https://docs.github.com/en/copilot/using-github-copilot/using-copilot-coding-agent)

## Troubleshooting

| Surface | Issue | Fix |
|---------|-------|-----|
| VS Code | Server doesn't appear | Check you used `servers` not `mcpServers` — they are silently incompatible |
| VS Code | Tools show but return errors | Check `Authorization` header has a valid token |
| Copilot CLI | `copilot mcp list` shows nothing | Check file path: `~/.copilot/mcp-config.json` for global, `.mcp.json` for project |
| Coding agent | Agent can't find tools | Ensure secret name starts with `COPILOT_MCP_` prefix |
| All | Silent failure | Validate JSON syntax — all surfaces fail silently on malformed JSON |