---
{
  "title": "CDN edge cache serves stale responses for minutes after deploy",
  "domain": "network",
  "tags": [
    "cdn",
    "cache",
    "deployment",
    "edge",
    "cloudflare"
  ],
  "status": "published",
  "evidence_level": "E2",
  "created": "2026-08-11 00:00:00 UTC",
  "updated": "2026-08-11 00:00:00 UTC",
  "author": "Liona Can",
  "source": "manual",
  "edited_at": "2026-08-21T13:12:59+08:00",
  "merged_by": "Liona Can"
}
---

# CDN edge cache serves stale responses for minutes after deploy

## Problem

After deploying a fix to a worker script, repeated requests still returned the old behaviour. Verifying the change "didn't work" wasted time until it was realized the CDN edge cache was still serving a stale snapshot.

## Root cause

A CDN (Cloudflare and similar) caches responses at the edge for a configurable TTL (~30–60 s in the observed case). Right after a deploy, the edge node closest to the requester can still hold and serve the previous version. Requests without a cache-busting parameter hit that stale copy, so the freshly deployed logic is invisible to the first several checks.

## Failure & recovery

The mistake was treating the first post-deploy request as a live verification. The recovery is cheap and reliable:

1. Add a random query parameter to force a cache miss: `?x=$RANDOM` (or `?ts=<epoch>`).
2. Disable browser/edge caching during verification (or use a curl one-shot with a unique query string).
3. Confirm the routed response carries the new revision before moving on.

## Principle: verify what you just shipped

Deployment verification must bypass the cache for the exact zone you changed. Without this, the engineer "proves" a regression that never existed and can even roll back a good deploy.

## Reusable checklist

- Always assume the edge is stale for the first N seconds/minutes.
- Use a unique query parameter when confirming behavior.
- Read `cf-cache-status`/response headers to see whether the reply came from the edge or origin.

## Lesson

"Deployed" and "served" are different states. Cache-bust the verification request, and read the cache-status header, before trusting that your new code is really live.
