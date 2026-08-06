# MisakaNet MCP Protocol Specification

## Overview

MisakaNet exposes its knowledge base via the Model Context Protocol (MCP).
Two server variants are available:

| Server | File | Capabilities |
|--------|------|-------------|
| Base | `integrations/mcp-server/server.py` | Tools only |
| Extended | `integrations/mcp-server/server_extended.py` | Tools + Resources |

## Protocol

- Transport: **stdio** (JSON-RPC 2.0, one message per line)
- Protocol version: `2024-11-05`
- Server name: `misakanet`
- Server version: `0.2.0`

## Tools

### search_lessons

Search the knowledge base with optional filters.

```json
{
  "name": "search_lessons",
  "arguments": {
    "query": "pip timeout proxy",
    "domain": "python",
    "tags": "timeout,network",
    "top_k": 5
  }
}
```

Returns: array of `{title, score, domain, path, preview}`

### get_lesson

Get full lesson content and metadata.

```json
{"name": "get_lesson", "arguments": {"id": "pip-timeout-fix"}}
```

Returns: `{id, path, title, domain, tags, content, word_count}`

### list_domains

List all knowledge domains with lesson counts.

Returns: `[{name, lesson_count}]`

### list_lessons

List lessons, optionally by domain.

```json
{"name": "list_lessons", "arguments": {"domain": "docker"}}
```

Returns: `[{id, path, title, domain}]` (max 50)

## Resources

### misakanet://domains

Static resource listing all domains.

### misakanet://lessons/{id}

Resource template — resolves to full lesson metadata + content.

Example: `misakanet://lessons/pip-timeout-fix`

## Client Configuration

### Cursor

Settings → MCP → Add Server:
```json
{
  "mcpServers": {
    "misakanet": {
      "command": "python3",
      "args": ["/path/to/MisakaNet/integrations/mcp-server/server_extended.py"]
    }
  }
}
```

### Claude Desktop

`claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "misakanet": {
      "command": "python3",
      "args": ["/path/to/MisakaNet/integrations/mcp-server/server_extended.py"]
    }
  }
}
```

### Claude Code

```bash
claude mcp add misakanet python3 /path/to/MisakaNet/integrations/mcp-server/server_extended.py
```

### Continue.dev

`.continue/config.json`:
```json
{
  "experimental": {
    "modelContextProtocolServers": [
      {
        "transport": {"type": "stdio", "command": "python3", "args": ["/path/to/server_extended.py"]}
      }
    ]
  }
}
```

## Error Handling

| Code | Meaning |
|------|---------|
| -32601 | Unknown method or tool |
| -32602 | Invalid params (e.g., unknown resource URI) |
| -32700 | Parse error (malformed JSON) |

## Requirements

- Python 3.10+
- `misakanet-core` package (`pip install misakanet-core`)
- MisakaNet repo cloned locally
