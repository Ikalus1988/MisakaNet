# MisakaNet

**Use MisakaNet when your coding agent hits an error** - Search 1M+ GitHub issues instantly via MCP.

[![Glama](https://img.shields.io/badge/Glama-MisakaNet-blue)](https://glama.ai/mcp/servers/misakanet)

## Quick Start

### Installation

```bash
npm install -g @misakanet/mcp-server
```

### Configuration

#### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%/Claude/claude_desktop_config.json` (Windows):

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

#### Cursor

Add to Cursor settings (Settings → Features → MCP):

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

### Restart Your Client

After adding the configuration:
- **Claude Desktop**: Quit and restart the application
- **Cursor**: Reload the window (Cmd/Ctrl + Shift + P → "Reload Window")

### First Query

Try this guaranteed-success test query:

```
Search MisakaNet for "database locked"
```

### Expected Output

You should see:
- A list of relevant GitHub issues related to "database locked" errors
- Issue titles, repositories, and URLs
- Snippets showing context around the error
- Direct links to solutions and discussions

## Available Tools

### `search_issues`

Search GitHub issues across 1M+ indexed repositories.

**Parameters:**
- `query` (string, required): Search terms (e.g., "database locked", "CORS error")
- `limit` (number, optional): Maximum results to return (default: 10, max: 50)

**Example:**
```
Search MisakaNet for "CORS policy blocked" with limit 5
```

## Use Cases

- Debug cryptic error messages by finding real-world solutions
- Discover how others solved similar problems
- Find relevant GitHub issues and discussions
- Get context-aware error resolution suggestions

## Features

- 🔍 **Instant Search**: Query 1M+ GitHub issues in milliseconds
- 🎯 **Relevant Results**: Semantic search finds contextually similar issues
- 🔗 **Direct Links**: Jump straight to GitHub discussions and solutions
- 🤖 **Agent-Ready**: Works seamlessly with Claude, Cursor, and other MCP clients

## Development

```bash
# Clone the repository
git clone https://github.com/misakanet/misakanet.git
cd misakanet

# Install dependencies
npm install

# Build
npm run build

# Test locally with MCP Inspector
npx @modelcontextprotocol/inspector node dist/index.js
```

## Troubleshooting

### Tool not appearing in Claude/Cursor

1. Verify the config file path is correct
2. Ensure JSON syntax is valid (no trailing commas)
3. Restart the client application completely
4. Check the MCP logs for errors

### No results returned

1. Try a more specific query (e.g., "sqlite database locked" instead of "error")
2. Check your internet connection
3. Verify the MCP server is running (check client logs)

## Contributing

Contributions welcome! Please read our contributing guidelines before submitting PRs.

## License

MIT

## Links

- [Glama Profile](https://glama.ai/mcp/servers/misakanet)
- [GitHub Repository](https://github.com/misakanet/misakanet)
- [MCP Documentation](https://modelcontextprotocol.io)
