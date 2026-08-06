---
{
  "title": "Timeout wrapper for runaway agent children",
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

# Timeout wrapper for runaway agent children

## Problem

Child python jobs run forever and pile up CPU.

## Root Cause

No wall-clock limit around subprocesses.

## Solution

```bash
timeout 120s python3 job.py || echo fail:$?
```

```python
import subprocess
subprocess.run(["python3","job.py"], timeout=120, check=False)
```

## Verification

```bash
timeout 1s sleep 5; echo exit:$?   # 124
```

## Notes

- Prefer cooperative cancellation inside long loops.

