---
{
  "title": "Handle API rate limits with exponential backoff",
  "domain": "devops",
  "tags": ["api", "rate-limit", "retry", "429", "backoff"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "translated_from": "lessons/contrib/api-rate-limit-handling.md",
  "created": "2026-07-21",
  "updated": "2026-07-21",
  "confidence": "0.9"
}
---

# Handle API rate limits with exponential backoff

> English translation of `lessons/contrib/api-rate-limit-handling.md`

## Problem

Third-party API calls return **HTTP 429** (Too Many Requests) or **403** under quota. Automation dies on the first rejection.

## Root Cause

Providers enforce per-minute / per-hour / per-day quotas. Scripts that retry immediately or ignore `Retry-After` thrash the limit and stay blocked.

## Solution

Use exponential backoff with jitter and honor `Retry-After` when present:

```python
import time
import random
import requests

def get_with_backoff(url, headers=None, max_tries=6):
    delay = 1.0
    for attempt in range(max_tries):
        r = requests.get(url, headers=headers or {}, timeout=30)
        if r.status_code not in (429, 503):
            r.raise_for_status()
            return r
        ra = r.headers.get("Retry-After")
        sleep_s = float(ra) if ra and str(ra).isdigit() else delay + random.uniform(0, 0.5)
        time.sleep(sleep_s)
        delay = min(delay * 2, 60)
    raise RuntimeError(f"rate limited after {max_tries} tries: {url}")
```

Also: cache GETs, batch writes, and spread cron jobs so many agents do not align on the same minute.

## Verification

```bash
# unit-test your wrapper with a mock 429 then 200
python3 -c 'print("backoff wrapper tests here")'
```

## Notes

- GitHub unauthenticated REST is about 60 req/hour — prefer a PAT.
- Do not tight-loop 429s; that extends bans.

### Extra operational detail

When rate limits or merge conflicts hit an agent overnight job, prefer failing closed with a clear log line rather than spinning. Persist the last successful artifact path, sleep with jitter, and resume. Document the exact HTTP status and response headers in the proof folder so the next run can tune backoff without guessing.

For production earn loops, pair this lesson with TaskBounty sniper idle behavior and Superteam credit gates: empty inventory is not a code failure.

