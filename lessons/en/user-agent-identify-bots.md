---
{
  "title": "Set a clear User-Agent on earn HTTP clients",
  "domain": "networking",
  "tags": ["http", "user-agent", "api", "agent", "ops"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "created": "2026-07-23",
  "updated": "2026-07-23",
  "confidence": "0.9"
}
---

# Set a clear User-Agent on earn HTTP clients

## Problem

APIs block default Python-urllib user agents or cannot rate-limit fairly across bots.

## Root Cause

Empty or generic `User-Agent` strings look like abuse scanners.

## Solution

```python
HEADERS = {
    "User-Agent": "HermesMoneymaker/1.0 (+earn-agent)",
    "Accept": "application/json",
}
```

```bash
curl -A "HermesMoneymaker/1.0" -fsS "$URL"
```

## Verification

```bash
curl -sI -A "HermesMoneymaker/1.0" https://example.com | head
```

## Notes

- Do not spoof a full browser UA when the site requires a real browser session (captcha).
- Include a version string so operators can correlate logs after deploys.

### Operator checklist

1. Apply the pattern in the earn loop first.
2. Log success/failure with SAST timestamps.
3. Keep secrets out of the log line.
4. Re-run the verification block after deploy.
