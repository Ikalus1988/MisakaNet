# Docker Usage Guide

## Overview

MisakaNet provides official Docker images hosted on GitHub Container Registry (GHCR) for easy deployment and testing.

## Image Information

- **Registry**: GitHub Container Registry (GHCR)
- **Image**: `ghcr.io/ikalus1988/misakanet:latest`
- **Base**: Alpine Linux (minimal footprint)
- **Updates**: Automatically built on releases

## Basic Usage

### Pull the Image

```bash
docker pull ghcr.io/ikalus1988/misakanet:latest
```

### Run Interactive Mode

```bash
docker run -i ghcr.io/ikalus1988/misakanet:latest
```

### Run with Auto-removal

```bash
docker run -i --rm ghcr.io/ikalus1988/misakanet:latest
```

## Advanced Configuration

### Volume Mounting

Mount local directories for persistent data or configuration:

```bash
# Mount configuration directory
docker run -i --rm \
  -v $(pwd)/config:/config \
  ghcr.io/ikalus1988/misakanet:latest

# Mount data directory
docker run -i --rm \
  -v $(pwd)/data:/data \
  ghcr.io/ikalus1988/misakanet:latest
```

### Environment Variables

Configure MisakaNet using environment variables:

```bash
docker run -i --rm \
  -e LOG_LEVEL=debug \
  -e CONFIG_PATH=/config/settings.json \
  ghcr.io/ikalus1988/misakanet:latest
```

### Network Configuration

For services that need network access:

```bash
# Use host network
docker run -i --rm --network host \
  ghcr.io/ikalus1988/misakanet:latest

# Expose specific ports
docker run -i --rm -p 8080:8080 \
  ghcr.io/ikalus1988/misakanet:latest
```

## MCP Server Integration

### Claude Desktop Configuration

Add to your Claude Desktop MCP configuration:

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

### With Custom Configuration

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
        "/path/to/config:/config",
        "-e",
        "CONFIG_PATH=/config/settings.json",
        "ghcr.io/ikalus1988/misakanet:latest"
      ]
    }
  }
}
```

## CI/CD Integration

### GitHub Actions

```yaml
name: MisakaNet Smoke Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Pull MisakaNet
        run: docker pull ghcr.io/ikalus1988/misakanet:latest
      
      - name: Run smoke test
        run: |
          docker run -i ghcr.io/ikalus1988/misakanet:latest <<EOF
          {"jsonrpc": "2.0", "method": "initialize", "id": 1}
          EOF
```

### GitLab CI

```yaml
test:
  image: docker:latest
  services:
    - docker:dind
  script:
    - docker pull ghcr.io/ikalus1988/misakanet:latest
    - docker run -i ghcr.io/ikalus1988/misakanet:latest --version
```

### Jenkins

```groovy
pipeline {
    agent any
    stages {
        stage('Test MisakaNet') {
            steps {
                sh 'docker pull ghcr.io/ikalus1988/misakanet:latest'
                sh 'docker run -i ghcr.io/ikalus1988/misakanet:latest --version'
            }
        }
    }
}
```

## Docker Compose

For multi-container setups:

```yaml
version: '3.8'

services:
  misakanet:
    image: ghcr.io/ikalus1988/misakanet:latest
    stdin_open: true
    volumes:
      - ./config:/config
      - ./data:/data
    environment:
      - LOG_LEVEL=info
      - CONFIG_PATH=/config/settings.json
    restart: unless-stopped
```

Run with:

```bash
docker-compose up -d
```

## Troubleshooting

### Image Pull Issues

If you encounter authentication issues:

```bash
# Login to GHCR (if using private images)
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin

# Then pull
docker pull ghcr.io/ikalus1988/misakanet:latest
```

### Container Logs

View container logs:

```bash
# Run in foreground to see logs
docker run -i ghcr.io/ikalus1988/misakanet:latest

# Or check logs of running container
docker logs <container-id>
```

### Resource Limits

Set memory and CPU limits:

```bash
docker run -i --rm \
  --memory="512m" \
  --cpus="1.0" \
  ghcr.io/ikalus1988/misakanet:latest
```

## Best Practices

1. **Always use `--rm`** for temporary containers to avoid clutter
2. **Pin versions** in production (use tags instead of `latest`)
3. **Use volume mounts** for persistent data
4. **Set resource limits** in production environments
5. **Use environment variables** for configuration instead of rebuilding images

## Security Considerations

- Run containers with minimal privileges
- Use read-only root filesystem when possible
- Scan images regularly for vulnerabilities
- Don't store secrets in images or environment variables in plain text

```bash
# Example: Run with security options
docker run -i --rm \
  --read-only \
  --security-opt=no-new-privileges \
  --cap-drop=ALL \
  ghcr.io/ikalus1988/misakanet:latest
```
