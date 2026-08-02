# MisakaNet

A powerful MCP (Model Context Protocol) server implementation.

## Quick Start

### Docker (Recommended for Quick Trial)

The fastest way to try MisakaNet:

```bash
docker pull ghcr.io/ikalus1988/misakanet:latest
docker run -i ghcr.io/ikalus1988/misakanet:latest
```

### Install from PyPI

```bash
pip install misakanet
```

### Install from Source

```bash
git clone https://github.com/Ikalus1988/misakanet.git
cd misakanet
pip install -e .
```

## Features

- Full MCP server implementation
- Docker container support via GHCR
- Easy integration with Claude Desktop
- CI/CD friendly
- Minimal dependencies

## Documentation

- [Installation Guide](docs/installation.md) - Detailed installation instructions
- [Docker Usage](docs/docker.md) - Docker-specific documentation
- [Configuration](docs/configuration.md) - Configuration options
- [Usage Examples](docs/usage.md) - Common use cases

## Use Cases

### Claude Desktop MCP Integration

Add to your Claude Desktop configuration:

```json
{
  "mcpServers": {
    "misakanet": {
      "command": "docker",
      "args": ["run", "-i", "--rm", "ghcr.io/ikalus1988/misakanet:latest"]
    }
  }
}
```

### CI/CD Smoke Testing

```yaml
steps:
  - run: docker pull ghcr.io/ikalus1988/misakanet:latest
  - run: docker run -i ghcr.io/ikalus1988/misakanet:latest --version
```

### Isolated Trial

Test without installing Python:

```bash
docker run -i --rm ghcr.io/ikalus1988/misakanet:latest
```

## Contributing

Contributions are welcome! Please read our contributing guidelines before submitting PRs.

## License

See [LICENSE](LICENSE) file for details.

## Support

For issues and questions, please use the [GitHub issue tracker](https://github.com/Ikalus1988/misakanet/issues).
