---
{
  "title": "Log timestamps in SAST for SA ops agents",
  "domain": "ops",
  "tags": ["ops", "timezone", "sast", "logging", "agent"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "created": "2026-07-23",
  "updated": "2026-07-23",
  "confidence": "0.9"
}
---

# Log timestamps in SAST for SA ops agents

## Problem

Logs mix UTC and local time; a "9am job" misses by two hours on Hetzner UTC boxes.

## Root Cause

Servers default to UTC; operators think in SAST (UTC+2, no DST).

## Solution

```bash
TZ=Africa/Johannesburg date '+%F %T %Z'
```

```python
from datetime import datetime, timezone, timedelta
SAST = timezone(timedelta(hours=2))
print(datetime.now(SAST).strftime("%Y-%m-%d %H:%M:%S SAST"))
```

Label human-facing log lines with a `SAST` suffix. Convert only at display edges.

## Verification

```bash
TZ=Africa/Johannesburg date
```

## Notes

- Prefer UTC inside databases; render SAST for the owner.
- Cron on UTC hosts: express schedules carefully or set `CRON_TZ`.

### Operator checklist

1. Apply the pattern in the earn loop first.
2. Log success/failure with SAST timestamps.
3. Keep secrets out of the log line.
4. Re-run the verification block after deploy.
