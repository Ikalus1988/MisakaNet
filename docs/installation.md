# Installation Guide

## Quick Start Options

### Option 1: Docker Container (Recommended for Quick Trial)

The easiest way to try MisakaNet without setting up Python locally is using our official Docker container from GitHub Container Registry (GHCR).

#### Pull and Run

```bash
docker pull ghcr.io/ikalus1988/misakanet:latest
docker run -i ghcr.io/ikalus1988/misakanet:latest
```

#### Use Cases

**1. Claude Desktop MCP Configuration**

To use MisakaNet as an MCP server with Claude Desktop, add this to your Claude Desktop configuration:

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

Configuration file locations:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

**2. CI/CD Smoke Testing**

Integrate MisakaNet into your CI pipeline for automated testing:

```yaml
# Example GitHub Actions workflow
steps:
  - name: Pull MisakaNet
    run: docker pull ghcr.io/ikalus1988/misakanet:latest
  
  - name: Run smoke test
    run: |
      docker run -i ghcr.io/ikalus1988/misakanet:latest <<EOF
      {"jsonrpc": "2.0", "method": "initialize", "id": 1}
      EOF
```

**3. Isolated Trial (No Local Python Setup)**

Test MisakaNet without installing Python or dependencies:

```bash
# Interactive mode
docker run -i ghcr.io/ikalus1988/misakanet:latest

# With volume mounting for persistent data
docker run -i -v $(pwd)/data:/data ghcr.io/ikalus1988/misakanet:latest

# With environment variables
docker run -i -e CONFIG_PATH=/config/settings.json ghcr.io/ikalus1988/misakanet:latest
```

### Option 2: Install from PyPI

For production use or development, install via pip:

```bash
pip install misakanet
```

### Option 3: Install from Source

For contributors or advanced users:

```bash
git clone https://github.com/Ikalus1988/misakanet.git
cd misakanet
pip install -e .
```

## System Requirements

- **Docker**: Version 20.10 or higher (for container option)
- **Python**: 3.8 or higher (for pip/source installation)
- **OS**: Linux, macOS, or Windows

## Verification

Verify your installation:

```bash
# For Docker
docker run -i ghcr.io/ikalus1988/misakanet:latest --version

# For pip installation
misakanet --version
```

## Next Steps

- See [Configuration Guide](configuration.md) for setup options
- Check [Usage Examples](usage.md) for common workflows
- Review [MCP Integration](mcp-integration.md) for Claude Desktop setup
