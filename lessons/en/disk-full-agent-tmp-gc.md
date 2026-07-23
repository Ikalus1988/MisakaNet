---
{
  "title": "Disk full from agent tmp dirs — GC pattern",
  "domain": "ops",
  "tags": ["disk", "tmp", "gc", "agent", "ops", "cleanup"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "created": "2026-07-22",
  "updated": "2026-07-22",
  "confidence": "0.9"
}
---

# Disk full from agent tmp dirs — GC pattern

## Problem

Agent machines fill `/tmp` or `work/runs` with screenshots, tarballs, and venvs. New jobs fail with `No space left on device`.

## Root Cause

Every job writes artifacts; nothing deletes old runs. Logs rotate poorly.

## Solution

```bash
# keep last 3 days of runs
find "$HOME/hermes-moneymaker/work/runs" -mindepth 1 -mtime +3 -exec rm -rf {} + 2>/dev/null || true
# large screenshots
find /tmp -name '*.png' -mtime +1 -size +1M -delete 2>/dev/null || true
df -h .
```

Cron weekly:

```cron
0 4 * * 0 find $HOME/hermes-moneymaker/work -name '*.tgz' -mtime +14 -delete
```

Prefer writing under a job-scoped `TMPDIR` that is deleted on success.

## Verification

```bash
df -h .
du -sh "$HOME/hermes-moneymaker/work"/* 2>/dev/null | sort -h | tail
```

## Notes

- Never delete `secrets/` or wallet files in GC.
- Keep proof folders for paid jobs until payout lands.
