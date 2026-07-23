---
{
  "title": "Split stdout/stderr in cron earn jobs",
  "domain": "ops",
  "tags": [
    "cron",
    "logging",
    "stderr",
    "ops",
    "agent"
  ],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "created": "2026-07-23",
  "updated": "2026-07-23",
  "confidence": "0.9"
}
---

# Split stdout/stderr in cron earn jobs

## Problem

Cron mails mix debug prints and real errors; failures hide in noise.

## Root Cause

Both streams append to one file without levels.

## Solution

```bash
mm-snipe >>"$LOGDIR/snipe.out" 2>>"$LOGDIR/snipe.err"
```

Alert only on non-empty `.err` or non-zero exit:

```bash
mm-snipe >"$LOGDIR/snipe.out" 2>"$LOGDIR/snipe.err" || echo FAIL >>"$LOGDIR/snipe.err"
```

## Verification

```bash
# force an error and confirm it lands in .err only
false 2>>/tmp/t.err; test -s /tmp/t.err && echo ok
```

## Notes

- Keep last 7 days of rotated logs.
- Idle empty-board messages belong on stdout, not stderr.

