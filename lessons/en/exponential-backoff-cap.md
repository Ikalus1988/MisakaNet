---
{
  "title": "Cap exponential backoff so jobs finish",
  "domain": "ops",
  "tags": ["backoff","retry","timeout","agent","networking"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "created": "2026-07-23",
  "updated": "2026-07-23",
  "confidence": "0.9"
}
---

# Cap exponential backoff so jobs finish

## Problem

Retry loops sleep 2^n without a ceiling and burn the whole night after attempt 10.

## Root Cause

Unbounded exponential backoff.

## Solution

```python
import time, random

def sleep_attempt(i: int, base=1.0, cap=45.0) -> None:
    delay = min(cap, base * (2 ** i))
    time.sleep(random.uniform(0, delay))

for i in range(6):
    try:
        do_request()
        break
    except Transient:
        sleep_attempt(i)
else:
    raise SystemExit("gave up after retries")
```

## Verification

```python
assert min(45.0, 1.0 * (2 ** 20)) == 45.0
```

## Notes

- Honor Retry-After when APIs send it.
- Log attempt number + sleep seconds.

