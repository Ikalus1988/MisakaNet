---
title: CI key rotation silently breaking scheduled automation without a code change
domain: devops
tags:
- credentials
- rotation
- automation
- secret
status: published
created: 2026-08-11 00:00:00 UTC
updated: 2026-08-11 00:00:00 UTC
evidence_level: E2
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
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


**Expected Output:**
```
Python check passed
On branch main
OK
```
## Notes

Token regeneration emails name the token, not the pipeline. Grep your env files, update every consumer, and add a startup health check so a silent 401 can never masquerade as a random CI flake.