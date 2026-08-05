{"title": "Multi-Forum Scraping Architecture — API vs Playwright", "domain": "ops", "subdomain": "scraping", "tags": ["scraping", "playwright", "api", "forum", "automation", "data-collection"], "source": "practical-experience", "status": "published", "confidence": "0.9", "created": "2026-07-01", "verified_date": "", "domain_expert": ""}


## Problem

Scraping multiple technical forums requires different approaches per site. Some have APIs, some require browser automation, some are behind anti-bot protection. Need a systematic way to choose and implement.

## Root Cause

Each forum has different:
- API availability (HN has Algolia, Dev.to has REST, most don't)
- Anti-bot protection (Cloudflare, login walls, rate limits)
- HTML structure (WoltLab, IPS Community, custom)
- Content format (structured Q&A vs long-form articles)

## Solution

### Decision Tree

```
Is there an API?
  ├─ Yes → Use API (JSON, structured, reliable)
  │         Examples: HN Algolia, Dev.to REST, GitHub API
  └─ No → Is the site behind anti-bot?
              ├─ Yes → Need browser automation (Playwright)
              │         Examples: robot-forum.com (WoltLab)
              └─ No → Try curl first, fall back to Playwright
                        Examples: Juejin, SegmentFault
```

### Implementation Patterns

#### Pattern 1: API-Based (Preferred)

```python
# HN Algolia API
import urllib.request, json
url = "https://hn.algolia.com/api/v1/search?query=MCP&tags=story&hitsPerPage=10"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=10) as resp:
    data = json.loads(resp.read())
    for hit in data["hits"]:
        print(f"[{hit['points']}↑] {hit['title']}")
```

Pros: Fast, structured, no browser overhead
Cons: Not all sites have APIs

#### Pattern 2: Playwright-Based

```javascript
const { chromium } = require('playwright');
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
await page.waitForTimeout(3000);  // Wait for JS rendering
const text = await page.evaluate(() => {
    const main = document.querySelector('#content, main');
    return main ? main.innerText : '';
});
```

Pros: Works on any site, handles JS rendering
Cons: Slower, needs browser binary, site-specific selectors

#### Pattern 3: Hybrid (API + Playwright)

Use API for listing/searching, Playwright for reading full content.

```
API → Get list of URLs → Playwright → Read each URL's content
```

### Site-Specific Findings

| Site | Method | Gotcha |
|------|--------|--------|
| HN | Algolia API | Use `tags=story` filter |
| Dev.to | REST API | Needs `User-Agent` header (403 without) |
| robot-forum.com | Playwright | WoltLab `ol.wbbThread` selector, `data-is-done` for resolved |
| Juejin | Playwright | Search requires login for full results |
| Reddit | ❌ Blocked | GFW SNI block, needs proxy |
| StackOverflow | ❌ 403 | Anti-bot |

### Rate Limiting

```
Between page loads:  2-3 seconds
Between API calls:   1 second
Per-site daily limit: ~500 pages (be respectful)
```

## Verification

1. API approach: `curl` returns JSON with expected structure
2. Playwright approach: `page.evaluate()` extracts text matching known content
3. Hybrid: API returns URLs, Playwright successfully loads each

## Notes

- Always check API availability before writing Playwright scrapers
- Playwright `domcontentloaded` is faster than `networkidle` for most sites
- Site-specific selectors change over time — build in fallback logic
- Store raw HTML/JSON for re-parsing when selectors break
