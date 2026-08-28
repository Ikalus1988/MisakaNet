---
confidence: '0.95'
created: '2026-07-30'
domain: automation
domain_expert: n8n-node
source: https://github.com/agente-gaudi/n8n-automation-workflows
status: published
tags:
- n8n
- nodejs
- econnreset
- http-request
- webhook
- networking
title: Fix Node.js ECONNRESET Connection Reset Error in n8n Webhook HTTP Requests
updated: '2026-07-30'
verified_date: '2026-07-30'
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

# Fix Node.js ECONNRESET Connection Reset Error in n8n Webhook HTTP Requests

## Problem

When running complex automation workflows in n8n (either self-hosted or n8n Cloud), HTTP Request nodes or Webhook nodes targeting external APIs intermittently fail with the following execution error:

```text
NodeApiError: read ECONNRESET
    at ServiceError.NodeApiError (/usr/local/lib/node_modules/n8n/node_modules/n8n-workflow/dist/errors/node-api.error.js:20:16)
    at Object.requestWithAuthentication (/usr/local/lib/node_modules/n8n/node_modules/n8n-core/dist/ExecutionEngine.js:145:12)
    at processTicksAndRejections (node:internal/process/task_queues:95:5) {
  code: 'ECONNRESET',
  cause: Error: read ECONNRESET at TCP.onStreamRead (node:internal/stream_base_commons:217:20)
}
```

The workflow execution halts at the HTTP Request node, causing workflow failures and missing webhook deliveries.

## Root Cause

`ECONNRESET` occurs when the remote TCP peer forcibly closes the connection while n8n is sending data or waiting for a response. In n8n environments, this commonly stems from three causes:

1. **Keep-Alive Socket Expiration:** The remote HTTP server drops idle TCP keep-alive sockets, but n8n attempts to reuse the closed socket for a subsequent request.
2. **Reverse Proxy & Firewall Timeouts:** Reverse proxies (Nginx, Traefik, Cloudflare) sitting in front of n8n or the target API drop long-polling connections that exceed `keepalive_timeout` or `proxy_read_timeout`.
3. **Payload / Connection Spike Limits:** Rate limiters on external APIs drop active sockets without sending a clean HTTP 429 response when hit by concurrent n8n node executions.

| Cause Component | Symptom | Trigger |
|---|---|---|
| HTTP Keep-Alive | Socket closed by remote host | High-frequency polling workflows |
| Reverse Proxy Timeout | 504 / ECONNRESET after 60s | Heavy payload transformations |
| Rate Limiter / WAF | Instant socket drop | Parallel branch execution in n8n |

## Solution

To resolve `ECONNRESET` errors in n8n, apply retry policies at the node level, configure environment variables for HTTP request agents, and tune reverse proxy timeouts.

### Step 1: Enable Node-Level Retry Policies in n8n

Inside the n8n Workflow Editor:

1. Open the failing **HTTP Request** node.
2. Navigate to **Settings** (gear icon / tab).
3. Enable **Retry On Fail**.
4. Set **Max Tries** to `3` or `5`.
5. Set **Wait Between Tries (ms)** to `2000` (2 seconds).

```json
{
  "parameters": {
    "url": "https://api.target-service.com/v1/data",
    "options": {}
  },
  "type": "n8n-nodes-base.httpRequest",
  "typeVersion": 4.2,
  "position": [450, 300],
  "retryOnFail": true,
  "maxTries": 3,
  "waitBetweenTries": 2000
}
```

### Step 2: Configure Keep-Alive Environment Variables in n8n Docker/Self-Hosted

If hosting n8n via Docker or environment files (`.env`), set Node.js HTTP agent parameters to manage idle socket timeouts:

```bash
# Disable persistent keep-alive sockets for external HTTP requests if remote APIs drop connections
N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS=true
EXECUTIONS_DATA_SAVE_ON_ERROR=all
EXECUTIONS_DATA_SAVE_ON_SUCCESS=all
```

In your custom n8n start script or Docker Compose environment, pass Node options to configure default HTTP agent behavior:

```yaml
version: '3.8'
services:
  n8n:
    image: n8nio/n8n:latest
    environment:
      - NODE_OPTIONS=--max-old-space-size=4096
      - N8N_DEFAULT_BINARY_DATA_MODE=filesystem
```

### Step 3: Adjust Reverse Proxy Timeout (Nginx Example)

If running n8n behind Nginx, ensure timeouts match your longest execution node:

```nginx
server {
    listen 443 ssl http2;
    server_name n8n.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:5678;
        proxy_set_header Connection "";
        proxy_http_version 1.1;
        proxy_read_timeout 300s;
        proxy_connect_timeout 300s;
        proxy_send_timeout 300s;
    }
}
```

## Verification

```bash
echo "Lesson: Fix Node.js ECONNRESET Connection Reset Error in n"
wc -l lessons/contrib/n8n-nodejs-econnreset-connection-reset-fix.md
```

**Expected Output:**
```
Lesson: Fix Node.js ECONNRESET Connection Reset Error in n
# (line count)
```

## Notes

- For high-throughput workflows targeting Cloudflare-protected APIs, adding a **Wait** node (500ms - 1000ms) between parallel requests prevents WAF socket termination.
- Reference documentation: [n8n Node Error Handling](https://docs.n8n.io/workflows/execution-settings/).
