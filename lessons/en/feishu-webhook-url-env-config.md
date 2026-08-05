---
{
  "title": "Feishu webhook URL via env config (not hardcode)",
  "domain": "integrations",
  "tags": ["feishu", "webhook", "env", "secrets", "bot"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "translated_from": "lessons/contrib/feishu-webhook-url-env-config.md",
  "created": "2026-07-22",
  "updated": "2026-07-22",
  "confidence": "0.9"
}
---

# Feishu webhook URL via env config (not hardcode)

## Problem

Bot notify code hardcodes a Feishu/Lark webhook. Secrets leak into git; rotating hooks requires code edits and re-deploy.

## Root Cause

Template samples paste full `https://open.feishu.cn/open-apis/bot/v2/hook/...` into source. Agents copy the sample into production.

## Solution

```bash
# .env (mode 600, never commit)
export FEISHU_WEBHOOK_URL='https://open.feishu.cn/open-apis/bot/v2/hook/REDACTED'
```

```python
import os, json, urllib.request

url = os.environ["FEISHU_WEBHOOK_URL"]
body = json.dumps({"msg_type": "text", "content": {"text": "job ok"}}).encode()
req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req, timeout=15) as r:
    print(r.status, r.read()[:200])
```

Fail closed if missing:

```python
if not os.environ.get("FEISHU_WEBHOOK_URL"):
    raise SystemExit("FEISHU_WEBHOOK_URL not set")
```

## Verification

```bash
test -n "$FEISHU_WEBHOOK_URL"
# send a test ping from a throwaway hook, not production
```

## Notes

- Prefer Telegram as default notify when the product owner mandates it.
- Store only in secrets files mode 600; redact in logs and lessons.
