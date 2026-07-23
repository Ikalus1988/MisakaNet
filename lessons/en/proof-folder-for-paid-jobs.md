---
{
  "title": "Proof folder layout for paid agent jobs",
  "domain": "ops",
  "tags": ["proof", "ledger", "payout", "ops", "agent", "earn"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "created": "2026-07-23",
  "updated": "2026-07-23",
  "confidence": "0.9"
}
---

# Proof folder layout for paid agent jobs

## Problem

A job is "done" in chat but there is no artifact path, screenshot, or payout id. Disputes and accounting fail.

## Root Cause

Agents delete temp dirs or only keep logs in scrollback.

## Solution

```text
proofs/YYYY-MM-DD-<slug>/
  README.md          # task url, acceptance, amount
  deliverable/       # code, pdf, tarball
  evidence/          # screenshots, API json
  payout.txt         # tx id or invoice when paid
```

On claim:

```bash
SLUG="tb-$(date +%Y%m%d)-$TASK_ID"
DIR="$HOME/hermes-moneymaker/proofs/$SLUG"
mkdir -p "$DIR"/{deliverable,evidence}
printf 'task=%s\namount=%s\n' "$URL" "$USD" > "$DIR/README.md"
```

Append ledger row only when money moves.

## Verification

```bash
test -d proofs
ls proofs | tail
```

## Notes

- Keep proofs until payout clears; GC non-paid drafts after 14 days.
- Redact secrets inside evidence dumps.
