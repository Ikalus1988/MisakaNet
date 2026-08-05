---
{
  "title": "Single-instance flock for shell snipers",
  "domain": "ops",
  "tags": ["flock","lock","cron","shell","agent","ops"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "created": "2026-07-23",
  "updated": "2026-07-23",
  "confidence": "0.9"
}
---

# Single-instance flock for shell snipers

## Problem

Two cron invocations of `mm-snipe` overlap and double-hit the same API.

## Root Cause

No mutual exclusion around the critical section.

## Solution

```bash
#!/usr/bin/env bash
set -euo pipefail
LOCK=${XDG_RUNTIME_DIR:-/tmp}/mm-snipe.lock
exec 9>"$LOCK"
if ! flock -n 9; then
  echo "skip: another sniper holds lock"
  exit 0
fi
# ... claim logic ...
```

## Verification

```bash
# terminal A
flock /tmp/t.lock -c 'sleep 30'
# terminal B should skip
flock -n /tmp/t.lock -c 'echo ran' || echo blocked
```

## Notes

- Pair with PID lockfiles in long-lived Python loops.
- Exit 0 on lock busy so cron does not alert spam.

