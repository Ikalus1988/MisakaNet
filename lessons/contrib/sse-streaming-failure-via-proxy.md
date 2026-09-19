---
title: "SSE streaming returns no data through reverse proxy"
domain: devops
tags: [sse, streaming, proxy, nginx, debugging, mcp]
status: published
created: '2026-09-15'
updated: '2026-09-16'
source: "intake #1555 — SSE calls to nano-gpt.com via OpenRouter SDK failed with content truncation"
evidence_level: E3
provenance:
  source: "intake"
  issue: "#1555"
---

## Problem

MCP SSE transport works locally but returns no streaming data when accessed through a reverse proxy (nginx, Caddy, Cloudflare). The connection opens, the initial endpoint event arrives, but tool-call responses never stream back — they either arrive all at once when the connection closes or not at all.

## Root Cause

**Proxy buffering vs client parsing mismatch.** The proxy buffers SSE chunks (holding partial `data:` lines) while the client waits for complete `data:` lines before parsing. Neither side advances:

- **nginx**: `proxy_buffering on` (default) holds chunks in memory buffers until the response ends
- **Cloudflare**: buffers first 4KB of response before forwarding
- **Client**: SSE spec says wait for complete `data:` line (terminated by `\n\n`), so partial chunks are invisible

The symptom looks like "no data" but the connection is alive — both sides are waiting on each other.

## Solution

Disable buffering at the proxy level:

```nginx
# nginx — disable proxy buffering for SSE endpoints
location /sse {
    proxy_pass http://backend:8000;
    proxy_buffering off;           # critical: don't buffer SSE chunks
    proxy_cache off;               # don't cache streaming responses
    proxy_read_timeout 86400s;     # SSE connections are long-lived
    chunked_transfer_encoding on;  # pass chunks through as-is
    proxy_set_header Connection ''; # disable keepalive pooling
}
```

For Caddy, use `flush_interval -1` to disable buffering.

Diagnose with curl to isolate the issue:

```bash
# Should show streaming data incrementally
curl -N http://localhost:8000/sse

# If local works but proxy doesn't, the proxy is buffering
curl -N https://your-proxy.example.com/sse
```

## Verification

```bash
# 1. Local SSE works
curl -N http://localhost:8000/sse &
LOCAL_PID=$!
sleep 3
kill $LOCAL_PID 2>/dev/null
# Should have received at least one event

# 2. Proxied SSE works (after nginx config change)
curl -N https://your-proxy.example.com/sse &
PROXY_PID=$!
sleep 3
kill $PROXY_PID 2>/dev/null
# Should receive events incrementally, not all at once

# 3. Verify nginx config
nginx -t
# Should show "syntax is ok"
```

## Prevention

- Test SSE through the production proxy path, not just locally
- Add monitoring: if an SSE connection sends no data for >30s, flag it
- Document proxy requirements in the SSE transport README
- Consider WebSocket fallback for environments where proxy config can't be changed