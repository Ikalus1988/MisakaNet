---
{
  "title": "Separate scout vs worker modes in earn agents",
  "domain": "ops",
  "tags": ["mode","scout","worker","safety","agent","ops"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "created": "2026-07-23",
  "updated": "2026-07-23",
  "confidence": "0.9"
}
---

# Separate scout vs worker modes in earn agents

## Problem

A research script accidentally claims paid tasks or spends credits during scouting.

## Root Cause

One binary with no mode gate; defaults are too powerful.

## Solution

```text
MODE=scout   # research only, write opportunities/
MODE=worker  # claim only if in APPROVED.md
MODE=halt    # stop money activity
```

```bash
mode=$(tr -d '\n' < MODE 2>/dev/null || echo scout)
if [[ "$mode" != "worker" ]]; then
  echo "scout/halt: no claim"
  exit 0
fi
```

## Verification

```bash
echo scout > MODE
# sniper must not claim
echo worker > MODE
# sniper may claim approved inventory only
```

## Notes

- Default missing MODE to scout.
- Keep APPROVED.md human-gated for spend-sensitive work.

