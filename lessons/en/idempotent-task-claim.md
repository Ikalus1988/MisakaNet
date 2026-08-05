---
{
  "title": "Idempotent task claim keys for snipers",
  "domain": "ops",
  "tags": ["idempotency", "claim", "sniper", "taskbounty", "agent"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "created": "2026-07-23",
  "updated": "2026-07-23",
  "confidence": "0.9"
}
---

# Idempotent task claim keys for snipers

## Problem

Two sniper ticks claim the same OPEN task, double-work, or confuse the board.

## Root Cause

No local claim ledger. Network retries replay POST claim.

## Solution

```python
from pathlib import Path
import json, time

LEDGER = Path.home() / ".local/state/earn/claims.json"

def already(task_id: str) -> bool:
    if not LEDGER.exists():
        return False
    data = json.loads(LEDGER.read_text())
    return task_id in data

def mark(task_id: str, meta: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(LEDGER.read_text()) if LEDGER.exists() else {}
    data[task_id] = {**meta, "ts": time.time()}
    LEDGER.write_text(json.dumps(data, indent=2))

def claim(task_id: str, do_claim) -> str:
    if already(task_id):
        return "skip"
    res = do_claim(task_id)
    mark(task_id, {"res": str(res)[:200]})
    return "claimed"
```

Use server idempotency keys when the API supports them.

## Verification

```bash
# second claim same id must skip
```

## Notes

- Pair with PID lock so only one sniper process runs.
- Empty OPEN board is not a claim bug — log idle and exit 0.
