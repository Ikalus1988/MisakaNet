---
{
  "title": "Tiny /healthz endpoint for agent services",
  "domain": "devops",
  "tags": ["healthcheck", "http", "ops", "monitoring", "agent"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "created": "2026-07-23",
  "updated": "2026-07-23",
  "confidence": "0.9"
}
---

# Tiny /healthz endpoint for agent services

## Problem

Supervisors cannot tell if a local earn dashboard or API is up. Restarts thrash blindly.

## Root Cause

Service has no cheap liveness probe; only full business routes.

## Solution

```python
from http.server import BaseHTTPRequestHandler, HTTPServer

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/healthz", "/health"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok\n")
        else:
            self.send_response(404)
            self.end_headers()
    def log_message(self, *args):
        pass

HTTPServer(("127.0.0.1", 8765), H).serve_forever()
```

Probe:

```bash
curl -fsS http://127.0.0.1:8765/healthz
```

## Verification

```bash
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8765/healthz
# 200
```

## Notes

- Bind localhost unless intentionally public.
- Separate readiness (deps up) from liveness (process up) when you grow.
