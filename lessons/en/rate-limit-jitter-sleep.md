---
{
  "title": "Add jitter to retry sleeps (avoid thundering herd)",
  "domain": "networking",
  "tags": ["retry", "jitter", "rate-limit", "backoff", "agent"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "created": "2026-07-23",
  "updated": "2026-07-23",
  "confidence": "0.9"
}
---

# Add jitter to retry sleeps (avoid thundering herd)

## Problem

Many sniper processes wake on the same cron second, hit 429 together, and back off on the same schedule forever.

## Root Cause

Fixed `sleep(2 ** attempt)` aligned across workers. No jitter.

## Solution

```python
import random, time

def backoff_sleep(attempt: int, base: float = 1.0, cap: float = 60.0) -> None:
    exp = min(cap, base * (2 ** attempt))
    delay = random.uniform(0, exp)  # full jitter
    time.sleep(delay)
```

For cron snipers, also offset the schedule:

```bash
# every minute but sleep 0-25s first
*/1 * * * * sleep $((RANDOM % 25)); mm-snipe
```

## Verification

```python
# delays should differ across calls
import statistics
# manual: print backoff values for attempt 3 a few times
```

## Notes

- Honor `Retry-After` header when present.
- Cap total attempts so jobs die loudly instead of looping all night.
