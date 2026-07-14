{"title": "Anti-Bot IP Ban — TLS Fingerprint Bypass with 7 Open-Source Tools", "domain": "ops", "subdomain": "scraping", "tags": ["anti-bot", "tls-fingerprint", "curl-cffi", "scrapling", "drissionpage", "nodriver", "camoufox", "scraping", "forum"], "source": "practical-experience", "status": "published", "confidence": "0.85", "created": "2026-07-14", "verified_date": "2026-07-14", "domain_expert": ""}


## Problem

Scraping forums triggers HTTP 403 "Access Temporarily Blocked" — IP-level ban from anti-bot systems. Different from GFW SNI blocking (which drops TLS handshake). Here the connection succeeds but the server rejects the request based on request fingerprint, rate, or IP reputation.

**Key distinction from GFW SNI block** (see `gfw-tls-sni-block-pattern.md`):
- GFW: TLS handshake times out (network layer)
- Anti-bot: HTTP 403 returned immediately (application layer)

## Root Cause

Anti-bot systems detect automated access via:
1. **TLS fingerprint mismatch** — Python requests/curl have distinctive JA3 fingerprints
2. **Request rate** — >10 req/min triggers rate limiting
3. **IP reputation** — Datacenter IPs flagged more than residential
4. **Header inconsistency** — TLS impersonated browser but UA string doesn't match

WoltLab-based forums (common in industrial automation communities) are particularly sensitive to rapid access patterns.

## Solution

### 7 Open-Source Bypass Tools (Smoke-Tested 2026-07)

**Tier 1 — HTTP TLS Fingerprint (lightweight, try first):**

```bash
# curl_cffi — drop-in requests replacement with Chrome TLS impersonation
pip install curl_cffi
```

```python
from curl_cffi import requests
r = requests.get("https://forum.example.com/", impersonate="chrome", timeout=15)
print(r.status_code, len(r.text))
```

```bash
# Scrapling — TLS + stealth + proxy rotation
pip install scrapling
```

```python
from scrapling import Fetcher
fetcher = Fetcher(auto_match=False)
page = fetcher.get("https://forum.example.com/", timeout=15)
print(page.status, len(page.body))  # Use .body not .text
```

**Tier 2 — Browser Anti-Detection (JS challenge scenarios):**

```bash
# DrissionPage — dual mode: Session(HTTP) + Chromium(browser)
pip install DrissionPage
```

```python
from DrissionPage import SessionPage
page = SessionPage()
page.get("https://forum.example.com/")
print(len(page.html))
```

```bash
# nodriver — undetected Chrome successor (⚠️ Python <3.14 only)
pip install nodriver

# Camoufox — anti-detect Firefox (needs: python -m camoufox fetch)
pip install camoufox
```

**Tier 3 — Playwright Patch:**

```bash
# rebrowser-patches — fix CDP Runtime.Enable leak
npm install -g rebrowser-patches
npx rebrowser-patches patch --packageName playwright-core
```

### Multi-Forum Smoke Test Results (3 tools × 6 forums)

| Forum | Platform | curl_cffi | Scrapling | DrissionPage |
|-------|----------|-----------|-----------|--------------|
| SegmentFault | Laravel | ✅ | ✅ | ✅ |
| Rclone Forum | Discourse | ✅ | ✅ | ✅ |
| cnblogs | Custom | ✅ | ✅ | ✅ |
| Industrial Forum | WoltLab | ✅ | ✅ | ✅ |
| V2EX | NodeBB | ❌ timeout | ❌ timeout | ❌ timeout |
| Hostloc | Discuz! | ❌ timeout | ❌ timeout | ❌ timeout |

**4/6 forums pass with all 3 tools.** V2EX/Hostloc timeouts are network-level (likely Cloudflare or GFW), not tool-related.

**Key finding**: All 3 HTTP tools have identical success/failure patterns per forum → the blocking is IP-based, not TLS-fingerprint-based. **Changing IP (proxy) is more effective than changing tool.**

### Polite Scraping Rules

```
Rate limit:     3-5s between requests, exponential backoff on 403/429
TLS-UA match:   Impersonated browser version must match User-Agent string
Session reuse:  Keep cookies, mimic human navigation (index→list→detail)
robots.txt:     Respect
Caching:        Cache locally to avoid re-requests
IP strategy:    Residential > Datacenter, rotate proxies
```

### Decision Flow

```
Target URL
  → Layer 1: Network reachable? (whitelist / curl TLS test)
  → Layer 2: Anti-bot? (HTTP 403? rate limit?)
  → Layer 3: Tool ready? (dependencies installed?)

  → All pass → curl_cffi direct
  → Network OK but blocked → curl_cffi → Scrapling+proxy → browser anti-detect
  → Network blocked → proxy or skip
```

## Verification

```bash
# Test curl_cffi against a forum
python3 -c "
from curl_cffi import requests
r = requests.get('https://bbs.gongkong.com/', impersonate='chrome', timeout=15)
print(f'Status: {r.status_code}, Length: {len(r.text)}')
"
# Expected: Status: 200, Length: >10000

# Test Scrapling
python3 -c "
from scrapling import Fetcher
f = Fetcher(auto_match=False)
p = f.get('https://bbs.gongkong.com/', timeout=15)
print(f'Status: {p.status}, Body: {len(p.body)}')
"
# Expected: Status: 200, Body: >100000
```

## Notes

- `curl_cffi` is the lowest-friction option — pip install, one line, no browser overhead
- `Scrapling` uses curl_cffi underneath but adds proxy rotation and stealth features
- `nodriver` has a Python 3.14 encoding bug in `network.py` — use Python 3.13
- `Camoufox` requires downloading a ~200MB Firefox binary (`python -m camoufox fetch`)
- For GFW-blocked sites (Reddit, SO), none of these work — you need a proxy (see `gfw-tls-sni-block-pattern.md`)
- This lesson complements `multi-forum-scraping-architecture.md` (API vs Playwright decision) and `scrapling-installation-and-usage.md` (Scrapling-specific)
