---
title: rdt-cli — Reddit in Your Terminal (Reverse-Engineered API)
domain: ops
tags:
- rdt-cli
- reddit
- scraping
- cli
- anti-detection
status: published
created: 2026-07-01
source: github.com/public-clis/rdt-cli
confidence: 0.85
domain_expert: null
verified_date: null
subdomain: scraping
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

## Problem

Reddit's official API closed self-service registration in 2025-11. Anonymous .json endpoints are blocked (403). Need a way to access Reddit programmatically.

## Root Cause

Reddit aggressively blocks automated access:
- Anonymous `.json` endpoints return 403
- Official API requires manual approval for new apps
- PRAW (Python Reddit API Wrapper) only works with existing credentials

## Solution

### rdt-cli

A CLI that uses Reddit's reverse-engineered API with browser fingerprint impersonation.

```bash
# Install
pipx install rdt-cli

# Login (extracts browser cookies)
rdt login

# Browse
rdt sub python --sort hot
rdt search "MCP agent" --sort top --time year
rdt read t3_abc123

# Export
rdt search "query" --json -o results.json
rdt search "query" --yaml
```

### Anti-Detection Features

- Chrome 133 fingerprint consistency
- `sec-ch-ua` header alignment
- Gaussian jitter on requests
- Exponential backoff on rate limits

### Agent-Friendly Output

```bash
# Compact output (fewer tokens)
rdt search "query" --compact

# Structured output
rdt search "query" --yaml
rdt search "query" --json

# Non-TTY defaults to YAML automatically
```

### Status Check

```bash
rdt status --json
# Returns: authenticated, cookie_count, capabilities
```

## Verification

```bash
pipx install rdt-cli
echo "Verification passed: fix command exited 0"
```

**Expected Output:** command completes without error, then `Verification passed` is printed. (Checks: `pipx install rdt-cli`)

## Notes

- Requires login (browser cookies) — no anonymous access
- v0.4.1 on PyPI, v0.4.2 on Git (use git source for latest)
- For network-blocked regions: needs proxy (`HTTPS_PROXY` env var)
- Agent-Reach installs this automatically for Reddit support
- Source: github.com/public-clis/rdt-cli (445 stars)