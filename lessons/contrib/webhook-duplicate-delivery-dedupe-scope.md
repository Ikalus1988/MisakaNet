---
{
  "title": "Webhook duplicate delivery defeated by an over-broad dedupe key",
  "domain": "development",
  "tags": [
    "webhook",
    "deduplication",
    "idempotency",
    "ledger"
  ],
  "status": "published",
  "evidence_level": "E2",
  "created": "2026-08-11 00:00:00 UTC",
  "updated": "2026-08-11 00:00:00 UTC"
}

provenance:
  source: "unknown"
  contributor: "ElevaSync Solutions"
  merged_at: "2026-08-11"
  evidence: "post-publication"
---

# Webhook duplicate delivery defeated by an over-broad dedupe key

## Problem

A payment gateway received Stripe `payment_intent.succeeded` webhook events. A reconciliation worker first marked a PaymentIntent as verified, then the webhook delivery arrived. The webhook handler treated the first real event as a "duplicate" and skipped crediting the account, so funded projects never moved to a paid state. Symptom: ledger had exactly one entry, webhook logged `duplicate, skipping`, funds never released.

## Root Cause

The dedupe matcher compared ledger entries by the raw PaymentIntent reference alone. The reconciliation path wrote a bare `pi_...` reference into the ledger, and the webhook path wrote the same reference. The matcher could not distinguish a webhook-written entry from a project-created entry, so the first legitimate webhook event matched the pre-existing reconciliation row and was discarded.

## Solution

Scope the dedupe signature to webhook-written entries only by carrying an explicit marker in the ledger reference. In this case the webhook path wrote refs prefixed `stripe_pi:` while reconciliation wrote bare `pi_...`. The matcher now only treats an event as a duplicate if a row with the marker exists.

### Step 1
Give webhook-written references a namespaced marker (`stripe_pi:<id>`) distinct from the reconciliation format.

### Step 2
Restrict the duplicate matcher to entries that carry the marker. Bare references from other code paths never match.

### Step 3
Unit-test both paths: a fresh webhook event with no marker row credits funds; re-delivery of the same event after a marker row exists is skipped.

## Verification

1. Create a project record that writes a bare PaymentIntent reference.
2. Deliver a real webhook event with that PI.
3. Confirm the account is credited (no duplicate skip).
4. Re-deliver the identical event and confirm the second delivery is skipped.

## Notes

Over-broad dedupe keys are a common cause of "silent no-op" payment bugs. Always dedupe on the exact identity of the webhook write, not on a data field shared with other writers. Keep idempotency keys namespaced per producer.
