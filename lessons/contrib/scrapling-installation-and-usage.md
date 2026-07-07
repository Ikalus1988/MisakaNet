---
title: Scrapling — Web Scraping Library with Anti-Detection
domain: ops
subdomain: scraping
tags:
- scrapling
- scraping
- curl-cffi
- playwright
- anti-detection
source: github.com/D4Vinci/Scrapling
status: published
confidence: '0.8'
created: '2026-07-01'
verified_date: ''
domain_expert: ''
---


## Problem

Standard scraping tools (requests, curl) are easily detected and blocked by anti-bot systems. Need a library that combines multiple fetching backends with anti-detection.

## Root Cause

Anti-bot systems check TLS fingerprints, User-Agent consistency, and request patterns. Standard Python requests library has a distinctive TLS fingerprint that's easily blocked.

## Solution

### Installation

```bash
# Create venv (required for externally-managed Python)
python3 -m venv scrapling-env
source scrapling-env/bin/activate

# Install with all dependencies
pip install "scrapling[all]"

# Key dependencies auto-installed:
# - curl_cffi (TLS fingerprint impersonation)
# - playwright (browser automation)
# - browserforge (header generation)
```

### Basic Usage

```python
from scrapling import Fetcher

fetcher = Fetcher()

# Simple GET
page = fetcher.get("https://example.com", timeout=15)
print(page.status)
print(page.css("title::text").get())

# With browser (for JS-heavy sites)
page = fetcher.get("https://example.com", headless=True)
print(page.text[:500])
```

### Architecture

scrapling uses curl_cffi underneath, which can impersonate browser TLS fingerprints. This helps bypass some anti-bot systems but does NOT bypass network-level blocks (GFW SNI filtering).

### When to Use

| Scenario | Use scrapling? |
|----------|---------------|
| Site has anti-bot (Cloudflare) | ✅ TLS fingerprint helps |
| Site is behind GFW | ❌ Same network path |
| Simple API endpoint | ❌ Use requests/curl |
| JS-heavy site | ✅ Playwright backend |

## Verification

1. `pip install "scrapling[all]"` succeeds
2. `from scrapling import Fetcher` imports without error
3. `fetcher.get("https://example.com")` returns 200

## Notes

- scrapling is NOT a replacement for Playwright — it's a higher-level wrapper
- curl_cffi impersonation helps with anti-bot but not network-level blocks
- For GFW-blocked sites, you still need a proxy regardless of scraping tool
- Source: github.com/D4Vinci/Scrapling (v0.4.9)
