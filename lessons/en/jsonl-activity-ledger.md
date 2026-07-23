---
{
  "title": "Append-only JSONL activity ledger for agents",
  "domain": "ops",
  "tags": [
    "ledger",
    "jsonl",
    "ops",
    "agent",
    "audit"
  ],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "created": "2026-07-23",
  "updated": "2026-07-23",
  "confidence": "0.9"
}
---

# Append-only JSONL activity ledger for agents

## Problem

Chat history is the only record of what the earn agent did; audits fail.

## Root Cause

No durable activity stream on disk.

## Solution

```python
import json, time
from pathlib import Path
path = Path.home()/ "hermes-moneymaker/ledger/activity.jsonl"

def log_event(action: str, **kw):
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": time.time(), "action": action, **kw}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
```

## Verification

```bash
tail -n 3 ~/hermes-moneymaker/ledger/activity.jsonl
```

## Notes

- Money events still need ledger.csv separately.
- Redact secrets before write.

