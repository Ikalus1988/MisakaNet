---
domain: "devops"
title: "GitHub API rate limiting returns 403 error"
verification: "metadata-normalized"
---
---{"title": "GitHub API rate limiting returns 403 error", "domain": "devops", "tags": ["github", "api", "rate-limit", "403", "python"]}---

## Problem

GitHub API calls fail with HTTP 403 when making unauthenticated requests beyond the rate limit (60/hour for unauthenticated, 5000/hour for authenticated).

## Root Cause

GitHub enforces rate limits per IP (unauthenticated) or per token (authenticated). Exceeding the limit returns a 403 with rate limit headers. Automated scraping scripts often hit this quickly.

## Fix

Always authenticate with a token to get 5000 requests/hour. Implement retry logic with exponential backoff using the `Retry-After` header. Check remaining limit via `https://api.github.com/rate_limit` before making bulk requests.

## Verification

Authenticated request to `https://api.github.com/rate_limit` returns `{'rate': {'remaining': 4999, 'limit': 5000}}`. Unauthenticated shows 60 limit.
