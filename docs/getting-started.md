# Getting Started with MisakaNet MCP

**Use MisakaNet when your coding agent hits an error** - Search 1M+ GitHub issues instantly.

## Installation

Install the MCP server globally:

```bash
npm install -g @misakanet/mcp-server
```

Or use it directly with npx (no installation required):

```bash
npx @misakanet/mcp-server
```

## Configuration

### Claude Desktop

1. Open your Claude Desktop configuration file:
   - **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows**: `%APPDATA%/Claude/claude_desktop_config.json`
   - **Linux**: `~/.config/Claude/claude_desktop_config.json`

2. Add the MisakaNet server configuration:

```json
{
  "mcpServers": {
    "misakanet": {
      "command": "npx",
      "args": ["-y", "@misakanet/mcp-server"]
    }
  }
}
```

3. If you already have other MCP servers configured, add MisakaNet to the existing `mcpServers` object:

```json
{
  "mcpServers": {
    "existing-server": {
      "command": "...",
      "args": ["..."]
    },
    "misakanet": {
      "command": "npx",
      "args": ["-y", "@misakanet/mcp-server"]
    }
  }
}
```

### Cursor

1. Open Cursor Settings:
   - Press `Cmd/Ctrl + ,` to open settings
   - Navigate to **Features** → **MCP**
   - Or use Command Palette: `Cmd/Ctrl + Shift + P` → "Preferences: Open Settings (JSON)"

2. Add the MisakaNet configuration:

```json
{
  "mcpServers": {
    "misakanet": {
      "command": "npx",
      "args": ["-y", "@misakanet/mcp-server"]
    }
  }
}
```

## Restart Your Client

After adding the configuration, you must restart your client:

### Claude Desktop
1. Quit Claude Desktop completely (Cmd/Ctrl + Q)
2. Relaunch the application
3. Wait for the MCP server to initialize (usually 2-5 seconds)

### Cursor
1. Reload the window: `Cmd/Ctrl + Shift + P` → "Developer: Reload Window"
2. Or restart Cursor completely
3. Wait for the MCP connection indicator to show "Connected"

## First Query

Once configured and restarted, try this guaranteed-success test query:

```
Search MisakaNet for "database locked"
```

You can also try:
- "Search MisakaNet for 'CORS policy blocked'"
- "Use MisakaNet to find solutions for 'connection timeout'"
- "Search for 'memory leak node.js' using MisakaNet"

## Expected Output

When you run your first query, you should see:

1. **Search Confirmation**: The agent acknowledges it's using the MisakaNet tool
2. **Results List**: A formatted list of relevant GitHub issues including:
   - Issue title
   - Repository name
   - Issue URL
   - Relevant snippets or context
   - Number of comments/reactions (if available)
3. **Summary**: The agent may summarize common solutions or patterns

Example output:
```
I found several relevant issues about "database locked" errors:

1. **SQLite database is locked** - microsoft/vscode#12345
   https://github.com/microsoft/vscode/issues/12345
   "Error: database is locked" when multiple processes access the same SQLite file.
   Solution: Use WAL mode or implement proper connection pooling.

2. **Database locked error in Electron app** - electron/electron#67890
   https://github.com/electron/electron/issues/67890
   Common issue with SQLite in Electron apps. Fixed by setting busy_timeout.

...
```

## Tool Reference

### `search_issues`

Search GitHub issues across 1M+ indexed repositories.

**Parameters:**
- `query` (string, required): Your search terms
  - Examples: "database locked", "CORS error", "memory leak"
- `limit` (number, optional): Maximum results to return
  - Default: 10
  - Maximum: 50

**Usage Examples:**

```
Search MisakaNet for "database locked"
Search MisakaNet for "CORS policy" with limit 20
Find GitHub issues about "webpack build failed"
```

## Troubleshooting

### MisakaNet tool not appearing

**Check 1: Configuration file**
- Verify the file path is correct for your OS
- Ensure JSON syntax is valid (use a JSON validator)
- No trailing commas in JSON

**Check 2: Client restart**
- Fully quit and restart the client (not just reload)
- Check client logs for MCP initialization errors

**Check 3: Installation**
- Run `npx @misakanet/mcp-server --version` to verify it can be executed
- Check for npm/node installation issues

### No results returned

**Try these fixes:**
1. Use more specific queries ("sqlite database locked" vs "error")
2. Check your internet connection
3. Verify the MCP server is running (check client logs)
4. Try a different query to rule out index issues

### Connection errors

**Common causes:**
- Firewall blocking npx/node
- Antivirus interfering with MCP communication
- Outdated Node.js version (requires Node 18+)

**Solutions:**
1. Update Node.js: `node --version` (should be 18.0.0 or higher)
2. Check firewall settings
3. Try running with local installation instead of npx

## Next Steps

- Explore more complex queries
- Combine MisakaNet with other MCP tools
- Integrate into your development workflow
- Check out [advanced usage examples](./advanced-usage.md)

## Support

- [GitHub Issues](https://github.com/misakanet/misakanet/issues)
- [Glama Profile](https://glama.ai/mcp/servers/misakanet)
- [MCP Documentation](https://modelcontextprotocol.io)
