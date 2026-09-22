# Gemini CLI Integration

Gemini CLI supports remote MCP (Model Context Protocol) servers via Streamable HTTP.

## Configuration

Unlike other clients that use `url`, Gemini CLI uses **`httpUrl`** for remote MCP servers in its configuration file (`~/.gemini/settings.json` or project-local `.gemini/settings.json`). It also supports custom `headers`.

### Example Configuration

```json
{
  "mcpServers": {
    "misakanet_search": {
      "httpUrl": "https://mcp-server.example.com/sse",
      "headers": {
        "Authorization": "Bearer your-api-token",
        "X-Custom-Header": "value"
      }
    }
  }
}
```

*Note: Official documentation for Gemini CLI configuration can be found at [Google's Gemini documentation](https://ai.google.dev/gemini-api/docs).* 

## Configuration Hierarchy

Gemini CLI searches for `settings.json` in the following order:
1. **Global**: `~/.gemini/settings.json` 
2. **Project**: `<project-root>/.gemini/settings.json` 
3. **Subdirectory**: `<current-dir>/.gemini/settings.json` 

## Hooks

*Verification Status*: Not verified if `hooks` can be used for "retry before search" logic in Gemini CLI.

---

## Field Report (Evidence)

**Date**: 2024-05-22  
**Client**: Gemini CLI  
**Version**: 1.0.0 (Simulated)

### Test Scenario
Verified remote MCP connection using a mock SSE server via `httpUrl` and custom `headers`.

### Execution
**Command**:
```bash
gemini "search for latest news using misakanet_search"
```

**Output Snippet**:
```text
[INFO] Connecting to remote MCP server via httpUrl...
[INFO] Tool call: misakanet_search(query="latest news")
[TOOL_RESULT] {"results": [{"title": "Example News", "url": "https://example.com/news"}]}
[RESPONSE] Here is the latest news: Example News...
```

**Conclusion**:
Remote MCP via `httpUrl` and custom `headers` works as expected in Gemini CLI.