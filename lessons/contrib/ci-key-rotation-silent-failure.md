---
{
  "\"title\"": "CI key rotation silently breaking scheduled automation without a code change\",",
  "\"domain\"": "devops\",",
  "\"tags\"": "[",
  "\"status\"": "published\",",
  "\"evidence_level\"": "E2\",",
  "\"created\"": "2026-08-11 00:00:00 UTC\",",
  "\"updated\"": "2026-08-11 00:00:00 UTC",
  "author": "ElevaSync Solutions",
  "source": "manual",
  "edited_at": "2026-08-11T03:00:00Z",
  "merged_by": "ElevaSync Solutions"
}
---

# CI key rotation silently breaking scheduled automation without a code change

## Problem

A scheduled automation job (dependency bot, deploy pipeline, or monitoring cron) started failing with `401 Unauthorized` / `Bad credentials` out of nowhere. No code changed, no configuration changed in the repo, and the local replacement key tested fine in the terminal.

## Root Cause

The personal access token (or long-lived secret) backing the automation was rotated/re-generated on the platform side. Automation was reading the old value from an environment file or CI secret that was never updated. The symptom is confusing because the newly generated key works interactively, masking that the automation still holds the stale copy.

## Solution

Treat secrets as versioned, discoverable artifacts with a single source of truth.

### Step 1
Verify where the automation actually reads the secret from (CI secret, env file, keyring) and confirm it still holds the old value:
```bash
grep -rn "ghp_\|gho_\|github_pat_" .env ci/ 2>/dev/null
```

### Step 2
Rotate in one place: put the new value into every consumer (`.env`, CI secrets, deploy config), not just one.

### Step 3
Add a cheap health check at automation start so stale credentials fail loudly:
```bash
curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $TOKEN" https://api.github.com/user | grep -q 200 || echo "[Error] token rejected"
```

### Step 4
If the platform lets you name tokens, give them a stable name (e.g. `automation-sezez`), so the security-event email tells you which pipeline to update.

## Verification

1. Rotated value present in every consumer (grep returns the new token everywhere).
2. Health check prints HTTP 200 after rotation.
3. Scheduled job runs clean for the next full cycle.

## Notes

Token regeneration emails name the token, not the pipeline. Grep your env files, update every consumer, and add a startup health check so a silent 401 can never masquerade as a random CI flake.
