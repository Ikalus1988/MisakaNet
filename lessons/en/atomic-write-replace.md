---
{
  "title": "Atomic file replace for agent status JSON",
  "domain": "ops",
  "tags": ["ops", "json", "atomic", "dashboard", "agent"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "created": "2026-07-23",
  "updated": "2026-07-23",
  "confidence": "0.9"
}
---

# Atomic file replace for agent status JSON

## Problem

Readers see half-written `data.json` while the dashboard refreshes and parse errors flash.

## Root Cause

In-place writes truncate the file before the new body is fully flushed.

## Solution

```python
from pathlib import Path
import os, json, tempfile

def atomic_write(path: Path, obj) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass
```

## Verification

```bash
python3 -c "from pathlib import Path; print(Path('dashboard').exists())"
```

## Notes

- Same temp+replace pattern works for markdown status files.
- Keep the temp file on the same filesystem as the destination.

### Operator checklist

1. Apply the pattern in the earn loop first.
2. Log success/failure with SAST timestamps.
3. Keep secrets out of the log line.
4. Re-run the verification block after deploy.
