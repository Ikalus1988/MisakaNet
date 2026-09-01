---
title: GitHub rate limiting hitting unauthenticated searches during automation
domain: network
tags:
- github
- rate-limit
- api
- automation
- token
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

# GitHub rate limiting hitting unauthenticated searches during automation

## Problem

A script that queries the GitHub API for issue/PR metadata suddenly returned `API rate limit exceeded` for the shared egress IP, even though the script had never hit the limit before. Local manual `curl` calls succeeded intermittently, making the failure appear random.

## Root Cause

The requests were unauthenticated, so they shared the anonymous per-IP quota (60 requests/hour) instead of the authenticated per-user quota. A burst of search calls (`/search/issues`, which is a separate, stricter budget) from the same egress IP exhausted the shared bucket. GitHub search endpoints have their own low limit (10/minute unauthenticated), which is easy to blow through in a loop.

## Solution

Authenticate every API call so you get the 5000/hour budget, and tune search call frequency.

### Step 1
Send an authorization header on every request:


**Expected Output:**
```
On branch main
OK
Found
```
## Notes

A stale or invalid token produces `Bad credentials` (401), which is different from `rate limit exceeded` (403/429). Check which one you are actually seeing before changing code. Keep the token out of logs and source — inject it via environment, never inline in the repo.