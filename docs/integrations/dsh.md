# dsh Integration

## Overview

MisakaNet integrates with dsh as a plugin, providing MCP (Model Context Protocol) tools and resources for AI agents.

## Available Tools

### misakanet_search

Search for lessons and content in the MisakaNet knowledge base.

```
Tool: misakanet_search
Parameters:
  - query (string): Search query
Returns: Array of matching lessons
```

### misakanet_get_lesson

Retrieve a specific lesson by ID.

```
Tool: misakanet_get_lesson
Parameters:
  - lesson_id (string): The lesson identifier
Returns: Lesson content and metadata
```

## Available Resources

### misaka://lessons/index

Access the complete lesson index.

```
URI: misaka://lessons/index
Type: application/json
Description: Complete index of all available lessons
```

## Usage with AI Agents

### Claude Code

MisakaNet works seamlessly with Claude Code through the MCP protocol.

### Cursor

Compatible with Cursor's MCP integration.

### Other MCP Agents

Any agent supporting the MCP protocol can use MisakaNet tools and resources.

## Configuration

No additional configuration required. Install the plugin and tools are automatically available.

## Troubleshooting

If tools are not appearing:

1. Verify plugin installation: `dsh plugin list`
2. Restart your agent
3. Check dsh version compatibility

## Integration Test Coverage

The repository includes a Node built-in test suite for the dsh plugin contract:

```bash
node --test tests/dsh/*.test.mjs
```

The suite covers:

- npm, git checkout, and manual file-copy installation paths
- MCP tool discovery and execution for `misakanet_search` and `misakanet_get_lesson`
- resource discovery/read access for `misaka://lessons/index`
- explicit error handling for unknown tools, missing lessons, and unknown resources
- Claude Code, Cursor, and generic MCP agent configuration compatibility
- startup latency and multiple in-flight JSON-RPC requests

CI runs these tests across Linux, macOS, and Windows with Node.js 18, 20, and 22.
