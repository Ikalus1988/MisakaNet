# Cursor Integration

Give Cursor access to 417 indexed failure lessons from MisakaNet.

Cursor (0.45+) supports the Model Context Protocol (MCP) directly, allowing it to seamlessly invoke tools provided by MisakaNet.

## Setup (Remote-First)

The easiest way to use MisakaNet is via the remote endpoint (no Python or local cloning required). 

1. Create or open `.cursor/mcp.json` in the root of your project.
2. Add the `misakanet` server configuration using the `sse` type:

{
  "mcpServers": {
    "misakanet": {
      "command": "https://api.misakanet.com/mcp",
      "type": "sse",
      "headers": {
        "Authorization": "Bearer YOUR_API_KEY"
      }
    }
  }
}

3. Save the file and restart Cursor.

### Difference between MCP and `.cursor/rules/*.mdc`
*   **Rules (`*.mdc`)**: Pure text guidelines injected into the context window.
*   **MCP (`mcp.json`)**: Active tool execution. Allows Cursor to dynamically search the database.

## Usage
In Cursor's AI chat, ask: "Search MisakaNet for DCO sign-off failure". Cursor will automatically detect the tool and run it.

## Troubleshooting
| Issue | Fix |
|-------|-----|
| "Silent failure / Tools not showing up" | You likely have a typo in the JSON keys. Cursor fails silently if the JSON schema is invalid. |
