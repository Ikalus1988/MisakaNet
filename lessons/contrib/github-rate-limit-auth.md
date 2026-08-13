---
{
  "\"title\"": "GitHub rate limiting hitting unauthenticated searches during automation\",",
  "\"domain\"": "network\",",
  "\"tags\"": "[",
  "\"status\"": "published\",",
  "\"evidence_level\"": "E2\",",
  "\"created\"": "2026-08-11 00:00:00 UTC\",",
  "\"updated\"": "2026-08-11 00:00:00 UTC",
  "author": "ElevaSync Solutions",
  "source": "manual",
  "edited_at": "2026-08-11T03:15:00Z",
  "merged_by": "ElevaSync Solutions"
}
---

# GitHub rate limiting hitting unauthenticated searches during automation

## Problem

A script that queries the GitHub API for issue/PR metadata suddenly returned `API rate limit exceeded` for the shared egress IP, even though the script had never hit the limit before. Local manual `curl` calls succeeded intermittently, making the failure appear random.

## Root Cause

The requests were unauthenticated, so they shared the anonymous per-IP quota (60 requests/hour) instead of the authenticated per-user quota. A burst of search calls (`/search/issues`, which is a separate, stricter budget) from the same egress IP exhausted the shared bucket. GitHub search endpoints have their own low limit (10/minute unauthenticated), which is easy to blow through in a loop.

## Solution

Authenticate every API call so you get the 5000/hour budget, and tune search call frequency.

### Step 1
Send an authorization header on every request:
```bash
curl -H "Authorization: Bearer $GHTOKEN" https://api.github.com/search/issues?q=repo:org/repo
```

### Step 2
Verify the real budget before assuming a bug:
```bash
curl -H "Authorization: Bearer $GHTOKEN" https://api.github.com/rate_limit | jq .resources.core
```
`remaining` should be ~5000, not 60.

### Step 3
Throttle search queries (10/min max, even authenticated) and add retry/backoff so a temporary limit does not kill the whole run.

## Verification

1. `rate_limit` shows `core.remaining` near 5000 after adding the header.
2. Search loop completes without `403/429`.
3. Re-run survives consecutive calls with no limit errors.

## Notes

A stale or invalid token produces `Bad credentials` (401), which is different from `rate limit exceeded` (403/429). Check which one you are actually seeing before changing code. Keep the token out of logs and source — inject it via environment, never inline in the repo.
