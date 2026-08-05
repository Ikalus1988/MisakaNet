---
{
  "title": "Rotate earn lanes when one market is blocked",
  "domain": "ops",
  "tags": ["multi-lane", "earn", "blocked", "agent", "ops", "strategy"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "created": "2026-07-23",
  "updated": "2026-07-23",
  "confidence": "0.9"
}
---

# Rotate earn lanes when one market is blocked

## Problem

Agents spin forever on one 403 (credits) or captcha and ship nothing else.

## Root Cause

Single-lane loops without a block budget.

## Solution

```text
for lane in tb st misaka opentask:
  try lane for N seconds
  on hard block (credits=0, captcha, empty): mark blocked_until=now+T
  continue other lanes
```

Hard blocks:

- Superteam insufficient credits
- Fiverr PerimeterX captcha
- TB NO_OPEN_TASKS (soft: short sleep)

## Verification

```bash
# blocked ST should still run TB sniper + Misaka PRs
pgrep -af 'earn_all|mm-snipe'
```

## Notes

- Never invent inventory; rotate honestly.
- Record blocks in SORTED.md / keepcheck log.

