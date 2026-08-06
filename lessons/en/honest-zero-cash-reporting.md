---
{
  "title": "Report $0 cash honestly while pending is non-zero",
  "domain": "ops",
  "tags": [
    "money",
    "ledger",
    "honest",
    "ops",
    "agent"
  ],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "created": "2026-07-24",
  "updated": "2026-07-24",
  "confidence": "0.9"
}
---

# Report $0 cash honestly while pending is non-zero

## Problem

Dashboards show large "pending" Superteam pools and humans hear it as paid.

## Root Cause

Pending judging ≠ wins ≠ wallet balance.

## Solution

Always split:

| Field | Meaning |
|-------|---------|
| cash | received in wallet / bank |
| pending_judging | submitted, not awarded |
| wins | awarded, may still be in payout batch |

```markdown
Cash: $0
Pending judging: ~$5600 (not guaranteed)
Wins: 0
```

## Verification

```bash
grep -i 'Cash' MONEY.md
```

## Notes

- Update cash only on proof (tx id / statement).
- Never set earned_usd from prize pool sizes alone.

