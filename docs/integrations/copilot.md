# GitHub Copilot MCP Integration

GitHub Copilot uses different configuration formats depending on the interface (surface) being used. Using the wrong key or file location will result in the MCP server failing to load silently.

## VS Code Copilot Chat
**Warning**: This surface uses the `servers` key. Using `mcpServers` will cause it to fail silently.

- **Key**: `servers` (NOT `mcpServers`)
- **Location**:
  - Project-specific: `.vscode/mcp.json`
  - User-wide: User profile `mcp.json`
- **Configuration Example**:
  ```json
  {
    "servers": {
      "everything": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-everything"]
      }
    }
  }
  ```

## Copilot CLI
- **Key**: `mcpServers`
- **Location**:
  - Global: `~/.copilot/mcp-config.json`
  - Project-specific: `.github/mcp.json` or `.mcp.json`
- **Configuration Example**:
  ```json
  {
    "mcpServers": {
      "everything": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-everything"]
      }
    }
  }
  ```
- **Field Report**:
  - **Status**: ✅ Verified
  - **Verification Method**: `copilot mcp list`
  - **Observation**: The server `everything` was correctly identified and listed by the CLI.

## GitHub.com Coding Agent
- **Key**: `mcpServers`
- **Location**: Repository Settings $\rightarrow$ Copilot $\rightarrow$ MCP (Web UI)
- **Constraint**: When using secrets in `headers` or `env` within the GitHub UI configuration, the values must reference secrets using the `COPILOT_MCP_` prefix (e.g., `COPILOT_MCP_MY_SECRET`).
- **Configuration Example (UI Input)**:
  ```json
  {
    "mcpServers": {
      "everything": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-everything"],
        "env": {
          "API_KEY": "COPILOT_MCP_MY_API_KEY"
        }
      }
    }
  }
  ```