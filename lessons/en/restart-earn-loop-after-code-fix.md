---
{
  "title": "Restart long-lived earn loops after code fixes",
  "domain": "ops",
  "tags": [
    "ops",
    "restart",
    "daemon",
    "agent",
    "deploy"
  ],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "created": "2026-07-24",
  "updated": "2026-07-24",
  "confidence": "0.9"
}
---

# Restart long-lived earn loops after code fixes

## Problem

You patch `earn_all.py` but the old process keeps running with the bug.

## Root Cause

Long-lived loop never reloads source.

## Solution

```bash
mm-desktop stop || true
# or
kill $(cat ~/.local/state/hermes-moneymaker/earn_loop.pid)
OPEN_BROWSER=0 mm-desktop start
pgrep -af 'earn_all.py loop'
```

## Verification

```bash
# confirm new pid and log line after fix
tail -5 ~/.local/state/hermes-moneymaker/earn_all.loop.log
```

## Notes

- Prefer start scripts that write pidfiles.
- Cron snipers pick up code each invocation automatically.

