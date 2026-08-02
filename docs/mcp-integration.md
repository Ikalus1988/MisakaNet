# MCP Integration Guide

## Overview

MisakaNet implements the Model Context Protocol (MCP) and can be integrated with MCP-compatible clients like Claude Desktop.

## Claude Desktop Integration

### Docker-based Setup (Recommended)

Using the Docker container is the simplest way to integrate MisakaNet with Claude Desktop.

#### Configuration

1. Locate your Claude Desktop configuration file:
   - **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
   - **Linux**: `~/.config/Claude/claude_desktop_config.json`

2. Add MisakaNet to your MCP servers:

```json
{
  "mcpServers": {
    "misakanet": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "ghcr.io/ikalus1988/misakanet:latest"
      ]
    }
  }
}
```

3. Restart Claude Desktop

#### With Custom Configuration

To use custom configuration files:

```json
{
  "mcpServers": {
    "misakanet": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-v",
        "/absolute/path/to/config:/config",
        "-e",
        "CONFIG_PATH=/config/settings.json",
        "ghcr.io/ikalus1988/misakanet:latest"
      ]
    }
  }
}
```

**Important**: Use absolute paths for volume mounts.

### Python-based Setup

If you have MisakaNet installed via pip:

```json
{
  "mcpServers": {
    "misakanet": {
      "command": "misakanet",
      "args": []
    }
  }
}
```

Or with Python module:

```json
{
  "mcpServers": {
    "misakanet": {
      "command": "python",
      "args": ["-m", "misakanet"]
    }
  }
}
```

## Environment Variables

Configure MisakaNet behavior through environment variables:

```json
{
  "mcpServers": {
    "misakanet": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-e",
        "LOG_LEVEL=debug",
        "-e",
        "TIMEOUT=30",
        "ghcr.io/ikalus1988/misakanet:latest"
      ],
      "env": {
        "CUSTOM_VAR": "value"
      }
    }
  }
}
```

## Available MCP Methods

MisakaNet supports the following MCP methods:

- `initialize` - Initialize the MCP connection
- `tools/list` - List available tools
- `tools/call` - Execute a tool
- `resources/list` - List available resources
- `resources/read` - Read a resource
- `prompts/list` - List available prompts
- `prompts/get` - Get a specific prompt

## Testing the Integration

### Verify Connection

1. Open Claude Desktop
2. Look for MisakaNet in the available MCP servers
3. Try a simple command that uses MisakaNet functionality

### Manual Testing

Test the MCP server directly:

```bash
# Using Docker
docker run -i ghcr.io/ikalus1988/misakanet:latest <<EOF
{"jsonrpc": "2.0", "method": "initialize", "params": {"protocolVersion": "0.1.0", "capabilities": {}}, "id": 1}
EOF
```

## Troubleshooting

### Server Not Appearing

1. Check configuration file syntax (valid JSON)
2. Verify file path is correct
3. Restart Claude Desktop completely
4. Check Claude Desktop logs

### Docker Permission Issues

**Linux/macOS**:
```bash
# Add user to docker group
sudo usermod -aG docker $USER
# Log out and back in
```

**Windows**:
- Ensure Docker Desktop is running
- Check Docker Desktop settings for WSL integration

### Connection Timeouts

Increase timeout in configuration:

```json
{
  "mcpServers": {
    "misakanet": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "ghcr.io/ikalus1988/misakanet:latest"],
      "timeout": 60000
    }
  }
}
```

### Volume Mount Issues

- Use absolute paths, not relative paths
- Ensure directories exist before mounting
- Check file permissions
- On Windows, use forward slashes: `C:/Users/...`

## Advanced Configuration

### Multiple Instances

Run multiple MisakaNet instances with different configurations:

```json
{
  "mcpServers": {
    "misakanet-dev": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-v", "/path/to/dev/config:/config",
        "ghcr.io/ikalus1988/misakanet:latest"
      ]
    },
    "misakanet-prod": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-v", "/path/to/prod/config:/config",
        "ghcr.io/ikalus1988/misakanet:latest"
      ]
    }
  }
}
```

### Resource Limits

Limit Docker container resources:

```json
{
  "mcpServers": {
    "misakanet": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "--memory=512m",
        "--cpus=1.0",
        "ghcr.io/ikalus1988/misakanet:latest"
      ]
    }
  }
}
```

## Best Practices

1. **Use Docker for isolation** - Keeps your system clean
2. **Pin versions in production** - Use specific tags instead of `latest`
3. **Use environment variables** - For configuration instead of rebuilding
4. **Monitor logs** - Check Claude Desktop logs for issues
5. **Test changes** - Verify configuration before deploying

## Security Considerations

- Don't expose sensitive data through environment variables
- Use read-only mounts when possible
- Limit container resources
- Keep Docker images updated
- Review MCP permissions granted to the server
