---
{
  "title": "Idle-exit cleanly when bounty boards are empty",
  "domain": "ops",
  "tags": ["idle", "sniper", "taskbounty", "cron", "agent", "ops"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "created": "2026-07-23",
  "updated": "2026-07-23",
  "confidence": "0.9"
}
---

# Idle-exit cleanly when bounty boards are empty

## Problem

Empty boards cause noisy errors and pager spam from cron.

## Root Cause

Snipers treat "0 OPEN" as failure (exit 1).

## Solution

```bash
out=$(python3 scripts/taskbounty_client.py open || true)
if echo "$out" | grep -q NO_OPEN_TASKS; then
  echo "idle: empty board"
  exit 0
fi
# else claim path
```

Log one idle line per tick; do not stack stacktraces.

## Verification

```bash
# with empty board
mm-snipe; echo exit:$?   # expect 0
```

## Notes

- Keep heartbeat metrics separate from error alerts.
- Still refresh payout method periodically while idle.

