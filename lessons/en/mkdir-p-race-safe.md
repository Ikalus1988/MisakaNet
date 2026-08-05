---
{
  "title": "Race-safe mkdir -p in parallel agents",
  "domain": "ops",
  "tags": ["ops", "agent", "shell", "reliability"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "created": "2026-07-23",
  "updated": "2026-07-23",
  "confidence": "0.9"
}
---

# Race-safe mkdir -p in parallel agents

## Problem

Two agents create the same work dir; one crashes on FileExistsError in code that used os.mkdir.

## Root Cause

Non-idempotent directory creation.

## Solution

```bash
mkdir -p "$WORK/out"
```

```python
from pathlib import Path
Path(work).mkdir(parents=True, exist_ok=True)
```

## Verification

```bash
mkdir -p /tmp/a/b; mkdir -p /tmp/a/b; echo ok
```

## Notes

- Still use PID locks for exclusive file writers.

