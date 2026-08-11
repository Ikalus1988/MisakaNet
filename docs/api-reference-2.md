# API Reference: Module 2

> Auto-generated documentation for Ikalus1988/MisakaNet

## Overview

This document describes the API surface for module 2 of the MisakaNet project.
All endpoints, types, and configuration options are documented below.

## Configuration

### Environment Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `MISAKANET_HOST` | string | `0.0.0.0` | Host address to bind |
| `MISAKANET_PORT` | integer | `8080` | Port number |
| `MISAKANET_LOG_LEVEL` | string | `info` | Logging verbosity |
| `MISAKANET_TIMEOUT` | integer | `30` | Request timeout (seconds) |
| `MISAKANET_MAX_BODY_SIZE` | string | `10mb` | Maximum request body size |
| `MISAKANET_CORS_ORIGINS` | string | `*` | Allowed CORS origins |
| `MISAKANET_RATE_LIMIT` | integer | `100` | Rate limit per minute |
| `MISAKANET_DB_URL` | string | - | Database connection URL |
| `MISAKANET_REDIS_URL` | string | - | Redis connection URL |
| `MISAKANET_SESSION_SECRET` | string | - | Session encryption key |

### Configuration File

```yaml
# MisakaNet.yaml
server:
  host: "0.0.0.0"
  port: 8080
  timeout: 30s
  max_body_size: 10mb

logging:
  level: info
  format: json
  output: stdout

cors:
  origins:
    - http://localhost:3000
    - https://misakanet.example.com
  methods:
    - GET
    - POST
    - PUT
    - DELETE
    - PATCH
  headers:
    - Content-Type
    - Authorization
    - X-Request-ID

rate_limit:
  enabled: true
  window: 60s
  max_requests: 100
```

## Core Types

### Request Context
```typescript
interface RequestContext {
  requestId: string;
  timestamp: number;
  userId?: string;
  sessionId?: string;
  traceId: string;
  metadata: Record<string, unknown>;
}
```

### Response Envelope
```typescript
interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: ApiError;
  meta: {
    requestId: string;
    timestamp: number;
    version: string;
  };
}
```

### Error Format
```typescript
interface ApiError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
  stack?: string;
}
```

## Health Check Endpoint

### GET /health

Returns the current health status of the service.

**Response:** `200 OK`
```json
{
  "status": "healthy",
  "uptime": 3600,
  "version": "1.0.0",
  "checks": {
    "database": "ok",
    "cache": "ok",
    "disk": "ok"
  }
}
```

## Metrics Endpoint

### GET /metrics

Exposes Prometheus-compatible metrics.

**Response:** `200 OK`
```
# HELP misakanet_requests_total Total request count
# TYPE misakanet_requests_total counter
misakanet_requests_total{method="GET",status="200"} 12345
misakanet_requests_total{method="POST",status="201"} 6789

# HELP misakanet_request_duration_seconds Request latency
# TYPE misakanet_request_duration_seconds histogram
misakanet_request_duration_seconds_bucket{le="0.01"} 100
misakanet_request_duration_seconds_bucket{le="0.05"} 500
misakanet_request_duration_seconds_bucket{le="0.1"} 1000
misakanet_request_duration_seconds_bucket{le="+Inf"} 12345
```

## Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Invalid request parameters |
| `AUTHENTICATION_ERROR` | 401 | Missing or invalid credentials |
| `AUTHORIZATION_ERROR` | 403 | Insufficient permissions |
| `NOT_FOUND` | 404 | Resource not found |
| `CONFLICT` | 409 | Resource already exists |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Unexpected server error |
| `SERVICE_UNAVAILABLE` | 503 | Service temporarily down |
| `GATEWAY_TIMEOUT` | 504 | Upstream timeout |

## Middleware Chain

1. **Request ID** — Assigns unique `X-Request-ID` to every request
2. **CORS** — Handles preflight and origin validation
3. **Authentication** — Validates JWT/API key tokens
4. **Rate Limiting** — Enforces per-client rate limits
5. **Body Parser** — Parses JSON, form, and multipart bodies
6. **Validation** — Validates request against schema
7. **Authorization** — Checks role-based permissions
8. **Logging** — Records request/response metadata
9. **Error Handler** — Catches and formats all errors
10. **Compression** — Gzip/brotli response compression

## Testing

### Unit Tests

```bash
# Run all unit tests
npm test

# Run with coverage
npm test -- --coverage

# Run specific test file
npm test -- api-reference.test.ts
```

### Integration Tests

```bash
# Start test environment
docker-compose -f docker-compose.test.yml up -d

# Run integration tests
npm run test:integration

# Cleanup
docker-compose -f docker-compose.test.yml down
```

### E2E Tests

```bash
# Run end-to-end tests
npm run test:e2e

# Run with specific browser
BROWSER=chromium npm run test:e2e
```

## Deployment

### Docker

```dockerfile
FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --production
COPY . .
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s CMD curl -f http://localhost:8080/health || exit 1
USER node
CMD ["node", "dist/main.js"]
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
      - name: misakanet
        image: misakanet:latest
        ports:
        - containerPort: 8080
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
```

## Monitoring

### Key Metrics

- **Request Rate**: requests per second by endpoint
- **Error Rate**: 4xx/5xx responses per second
- **Latency**: p50, p95, p99 response times
- **Saturation**: CPU, memory, goroutines/threads
- **Business**: user signups, payments, actions

### Alerting Rules

```yaml
alerts:
  - name: HighErrorRate
    expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
    severity: critical
    message: "Error rate above 5% for 5 minutes"

  - name: HighLatency
    expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 1
    severity: warning
    message: "p95 latency above 1s for 5 minutes"

  - name: ServiceDown
    expr: up == 0
    severity: critical
    message: "Service is not reachable"
```

## Changelog

### v1.0.0
- Initial API release
- Health check endpoint
- Metrics endpoint
- Full middleware chain

### v2.0.0 (Planned)
- WebSocket support
- GraphQL endpoint
- gRPC support
- OpenTelemetry tracing
