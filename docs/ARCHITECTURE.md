# MisakaNet — Architecture & Developer Guide

## Overview

MisakaNet is a distributed MCP (Model Context Protocol) gateway that enables seamless integration between LLM agents and network services. It provides a unified interface for routing, authentication, and protocol translation.

## System Architecture

```
┌─────────────┐     ┌─────────────┐     ┌──────────────────┐
│  LLM Agent  │────▶│  MisakaNet  │────▶│  MCP Servers      │
│  (Client)   │     │  Gateway    │     │  • Tool Server    │
└─────────────┘     │             │     │  • Resource Server│
                    │  • Router   │     │  • Prompt Server  │
                    │  • Auth     │     └──────────────────┘
                    │  • Cache    │
                    └─────────────┘
```

## Core Components

### 1. Gateway Router
Routes incoming MCP requests to appropriate backend servers based on method, resource URI, or tool name.

- **Method-based routing**: `tools/call`, `resources/read`, `prompts/get`
- **URI-based routing**: Wildcard patterns, prefix matching
- **Load balancing**: Round-robin, least-connections, weighted distribution

### 2. Authentication Layer
Handles OAuth2 client credentials flow and API key validation.

- **OAuth2**: Authorization code grant, client credentials
- **API Keys**: Scoped keys with rate limiting
- **JWT**: RS256 symmetric key validation

### 3. Protocol Translation
Translates between MCP JSON-RPC and backend-specific protocols (REST, gRPC, GraphQL).

### 4. Observability
- **Metrics**: Prometheus-compatible counters, histograms, gauges
- **Tracing**: OpenTelemetry distributed tracing
- **Logging**: Structured JSON logging with correlation IDs

## API Reference

### Health Check
```
GET /health
Response: { "status": "ok", "version": "1.0.0", "uptime": 3600 }
```

### List Tools
```
POST /mcp/tools/list
Response: { "tools": [...] }
```

### Call Tool
```
POST /mcp/tools/call
Body: { "name": "tool_name", "arguments": {} }
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MISAKA_PORT` | `8080` | Gateway listen port |
| `MISAKA_LOG_LEVEL` | `info` | Logging level |
| `MISAKA_AUTH_ENABLED` | `true` | Enable authentication |
| `MISAKA_RATE_LIMIT` | `100` | Requests per minute per client |
| `MISAKA_CACHE_TTL` | `300` | Cache TTL in seconds |
| `MISAKA_MAX_BODY_SIZE` | `1048576` | Max request body size |
| `MISAKA_TIMEOUT` | `30` | Backend timeout seconds |

## Development

### Prerequisites
- Node.js >= 18
- npm >= 9
- Docker (optional)

### Local Setup
```bash
git clone https://github.com/Ikalus1988/MisakaNet.git
cd MisakaNet
npm install
cp .env.example .env
npm run dev
```

### Running Tests
```bash
npm test
npm run test:coverage
npm run test:e2e
```

### Building
```bash
npm run build
npm run build:docker
```

## Deployment

### Docker
```bash
docker build -t misakanet .
docker run -p 8080:8080 misakanet
```

### Kubernetes
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: misakanet
spec:
  replicas: 3
  selector:
    matchLabels:
      app: misakanet
  template:
    metadata:
      labels:
        app: misakanet
    spec:
      containers:
      - name: gateway
        image: misakanet:latest
        ports:
        - containerPort: 8080
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feat/amazing-feature`)
3. Commit your changes (`git commit -m 'feat: add amazing feature'`)
4. Push to the branch (`git push origin feat/amazing-feature`)
5. Open a Pull Request

## License

See [LICENSE](LICENSE) file for details.
