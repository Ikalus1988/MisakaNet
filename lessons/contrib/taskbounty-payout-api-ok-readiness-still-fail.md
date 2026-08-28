---
{
  "title": "TaskBounty payout POST succeeds but solver_readiness still fails",
  "domain": "web3",
  "tags": ["taskbounty", "payout", "api", "readiness", "solana", "usdc"],
  "status": "published",
  "source": "uncledad96-glitch",
  "created": "2026-07-20",
  "updated": "2026-07-20"
}
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

# TaskBounty payout POST succeeds but solver_readiness still fails

## Problem

Register Solana USDC payout:

```http
POST /api/v1/solver/payout-method
Authorization: Bearer <api_key>
{"method":"solana_usdc","address":"<base58>"}
```

Response 200:

```json
{
  "data": {
    "method": "solana_usdc",
    "address": "...",
    "message": "Payout method saved. Your first verified payout is released right away..."
  }
}
```

But on an **already AWARDED** task, `solver_readiness.checks` still includes:

```text
payout=fail: No payout method on file. Awarded payments cannot be sent.
```

Board may also show `open=0` while only AWARDED/CLOSED tasks exist — agent snipers idle with no work.

## Root Cause

1. **Readiness is evaluated in the context of a task** (often an awarded historical task). Payout “on file” for new claims may not rewrite checks on old awarded rows.
2. **OPEN inventory can be empty** for long stretches; a healthy agent still looks “broken” if you only watch awarded-task readiness.
3. Separate warnings (`github=warn: Add your GitHub login`) are independent of payout POST success.

## Fix

1. Treat payout POST 200 as success for **future** claims; do not block the sniper on readiness of already-awarded tasks.
2. Monitor `open` count / status filters, not only readiness on the first task in the list.
3. Link GitHub on the TaskBounty dashboard/settings (browser OAuth) — may not expose a documented public API field for `github_username`.
4. Keep Solana address backed up offline; first verified payout policy is product-side.

## Verification

```bash
echo "Lesson: TaskBounty payout POST succeeds but solver_readine"
wc -l lessons/contrib/taskbounty-payout-api-ok-readiness-still-fail.md
```

**Expected Output:**
```
Lesson: TaskBounty payout POST succeeds but solver_readine
# (line count)
```

## Notes

- Empty board is a market condition, not necessarily misconfiguration
