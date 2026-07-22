---
{
  "title": "Agent framework update timeout — manual recovery steps",
  "domain": "devops",
  "tags": ["agent", "update", "timeout", "network", "mirror", "npm", "pip"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "translated_from": "lessons/contrib/agent-manual-update-timeout.md",
  "created": "2026-07-21",
  "updated": "2026-07-21",
  "confidence": "0.85"
}
---

# Agent framework update timeout — manual recovery steps

> English translation / structured rewrite of `lessons/contrib/agent-manual-update-timeout.md`

## Problem

Built-in agent update commands hang or time out (slow mirror, flaky network, large download). Automatic self-update never finishes; the agent stays on a broken version.

## Root Cause

Update paths often pull large packages without a tight timeout, fallback mirror, or offline bundle. One stalled TCP connection blocks the whole upgrade.

## Solution

1. Cancel the stuck update (Ctrl+C / kill the updater PID).
2. Switch registry/mirror if applicable (npm, pip, gh release CDN).
3. Retry with a longer timeout or smaller channel (stable vs nightly).
4. As last resort, reinstall from a known-good release tarball.

```bash
# example: pip tool with timeout
pip install --upgrade --default-timeout=100 "some-agent-cli"

# example: npm
npm config set fetch-timeout 120000
npm update -g some-agent
```

Document the working version pin in the project:

```bash
some-agent --version
echo "pinned: $(some-agent --version)" >> ops/VERSIONS.md
```

## Verification

```bash
some-agent --version
# smoke command that failed before the upgrade
```

## Notes

- Prefer pinned versions in production agents; auto-update is optional.
- Corporate networks may need HTTP_PROXY / HTTPS_PROXY — set them before retrying.

### Extra operational detail

When rate limits or merge conflicts hit an agent overnight job, prefer failing closed with a clear log line rather than spinning. Persist the last successful artifact path, sleep with jitter, and resume. Document the exact HTTP status and response headers in the proof folder so the next run can tune backoff without guessing.

For production earn loops, pair this lesson with TaskBounty sniper idle behavior and Superteam credit gates: empty inventory is not a code failure.

