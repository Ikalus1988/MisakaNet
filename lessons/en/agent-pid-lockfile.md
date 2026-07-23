---
{
  "title": "PID lockfile so earn loops do not double-run",
  "domain": "ops",
  "tags": ["lock", "pid", "cron", "daemon", "agent", "concurrency"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "created": "2026-07-22",
  "updated": "2026-07-22",
  "confidence": "0.9"
}
---

# PID lockfile so earn loops do not double-run

## Problem

Cron and a desktop starter both launch `earn_all.py`, fighting for the same lock, double-submitting, or skipping forever.

## Root Cause

No single-owner process identity. Stale lock files after crashes block new runs if PID checks are missing.

## Solution

```python
from pathlib import Path
import os, time

LOCK = Path.home() / ".local/state/app/job.lock"

def acquire(stale_sec: int = 600) -> bool:
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    if LOCK.exists():
        try:
            pid = int(LOCK.read_text().strip().split()[0])
            age = time.time() - LOCK.stat().st_mtime
            if Path(f"/proc/{pid}").exists() and age < stale_sec:
                return False
        except Exception:
            pass
    LOCK.write_text(f"{os.getpid()} {time.time()}
")
    return True

def release() -> None:
    try:
        if LOCK.exists() and str(os.getpid()) in LOCK.read_text():
            LOCK.unlink()
    except Exception:
        pass
```

Prefer one long-lived loop (`mm-desktop start`) plus a thin sniper cron — not two heavy loops.

## Verification

```bash
pgrep -af earn_all.py
cat ~/.local/state/hermes-moneymaker/earn_loop.pid
```

## Notes

- On kill -9, stale takeover by mtime/PID is required.
- Log "skip: lock held by pid=N" instead of silent exit.
