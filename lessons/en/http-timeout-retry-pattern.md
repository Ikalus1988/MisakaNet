---
{
  "title": "HTTP client timeout + retry pattern for agents",
  "domain": "networking",
  "tags": ["http", "timeout", "retry", "urllib", "agent", "resilience"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "created": "2026-07-22",
  "updated": "2026-07-22",
  "confidence": "0.9"
}
---

# HTTP client timeout + retry pattern for agents

## Problem

Overnight earn agents hang forever on a dead HTTP peer, or fail once on a blip and abandon a good job.

## Root Cause

Default sockets may block indefinitely. Single-shot requests treat transient 502/429 as fatal.

## Solution

```python
import json, time, urllib.error, urllib.request

def get_json(url: str, headers: dict | None = None, tries: int = 4, timeout: float = 20.0):
    last = None
    for i in range(tries):
        req = urllib.request.Request(url, headers=headers or {"User-Agent": "agent/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 500, 502, 503, 504) and i + 1 < tries:
                time.sleep(min(30, 2 ** i))
                continue
            raise
        except Exception as e:
            last = e
            if i + 1 < tries:
                time.sleep(min(30, 2 ** i))
                continue
            raise
    raise last  # type: ignore
```

## Verification

```bash
python3 -c "import urllib.request; urllib.request.urlopen('https://example.com', timeout=10); print('ok')"
```

## Notes

- Cap total wall time per job (e.g. 120s) separate from per-request timeout.
- Log status codes; do not log secrets from headers.
