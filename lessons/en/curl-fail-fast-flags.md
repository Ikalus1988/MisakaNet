---
{
  "title": "curl fail-fast flags for agent scripts",
  "domain": "ops",
  "tags": ["ops", "agent", "shell", "reliability"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "created": "2026-07-23",
  "updated": "2026-07-23",
  "confidence": "0.9"
}
---

# curl fail-fast flags for agent scripts

## Problem

curl hangs or follows bad redirects; scripts look stuck.

## Root Cause

Default curl has long timeouts and silent failures without `-f`.

## Solution

```bash
curl -fsS --connect-timeout 10 --max-time 30 -A "agent/1.0" "$URL" -o out.json
echo exit:$?
```

## Verification

```bash
curl -fsS --max-time 10 https://example.com >/dev/null && echo ok
```

## Notes

- `-f` fails on HTTP errors; pair with retries + jitter.

