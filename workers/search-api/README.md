# MisakaNet Search API Worker

REST API endpoints for lesson search, enabling MCP servers, editors, and other tools to integrate with MisakaNet.

## Endpoints

### GET /api/health

Health check endpoint.

**Response:**
```json
{
  "status": "ok",
  "service": "misakanet-search-api",
  "version": "1.0.0",
  "timestamp": "2026-07-17T12:00:00.000Z",
  "features": {
    "search": true,
    "rateLimit": true,
    "rateLimitRequests": 60,
    "rateLimitWindowSeconds": 60
  }
}
```

### GET /api/search

Search lessons with optional filters.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| q | string | required | Search query |
| domain | string | null | Filter by domain (e.g., `kubernetes`, `devops`) |
| tags | string | [] | Filter by tags (comma-separated, AND logic) |
| status | string | null | Filter by status (e.g., `published`, `draft`) |
| limit | number | 10 | Results per page (max 100) |
| offset | number | 0 | Pagination offset |

**Example:**
```bash
# Basic search
curl "https://misakanet-search-api.workers.dev/api/search?q=kubernetes"

# With filters
curl "https://misakanet-search-api.workers.dev/api/search?q=devops&domain=kubernetes&limit=5"

# Pagination
curl "https://misakanet-search-api.workers.dev/api/search?q=docker&limit=10&offset=20"
```

**Response:**
```json
{
  "query": "kubernetes",
  "filters": {
    "domain": "kubernetes",
    "tags": null,
    "status": null
  },
  "pagination": {
    "offset": 0,
    "limit": 10,
    "hasMore": true
  },
  "results": [
    {
      "title": "Deploy to Kubernetes",
      "domain": "kubernetes",
      "tags": ["devops", "deployment"],
      "status": "published",
      "score": 0.95,
      "path": "lessons/kubernetes/deploy.md",
      "preview": "Learn how to deploy applications to Kubernetes clusters..."
    }
  ],
  "total": 42,
  "rateLimitRemaining": 59
}
```

## Rate Limiting

- **Unauthenticated:** 60 requests per minute per IP
- Rate limit headers included in response:
  - `X-RateLimit-Limit`: Maximum requests per window
  - `X-RateLimit-Remaining`: Remaining requests
  - `X-RateLimit-Reset`: Unix timestamp when limit resets

## Deployment

1. Install dependencies:
```bash
npm install
```

2. Configure wrangler:
```bash
npx wrangler secret put GH_TOKEN  # If using GitHub features
```

3. Deploy:
```bash
npx wrangler deploy
```

## Development

Run locally:
```bash
npx wrangler dev
```

Run tests:
```bash
npm test
```

## Architecture

This worker provides HTTP endpoints that wrap the MisakaNet search engine. It:

1. Validates and parses incoming requests
2. Applies rate limiting per IP
3. Calls the search engine with filters
4. Returns paginated JSON results
5. Adds CORS headers for cross-origin access

## See Also

- [MisakaNet Protocol](https://github.com/Ikalus1988/MisakaNet)
- [MisakaNet CLI](https://github.com/Ikalus1988/MisakaNet#misakanet)
