---
domain: "scraping"
title: "V2EX API /api/topics/show.json Unstable — Use r.jina.ai Instead"
verification: "metadata-normalized"
{"title": "V2EX API /api/topics/show.json Unstable — Use r.jina.ai Instead", "domain": "scraping", "tags": ["v2ex", "api", "json-parse-error", "jina-reader", "fallback-strategy", "agent-reach"], "status": "published", "confidence": "0.85", "created": "2026-07-03", "updated": "2026-07-03", "source": "Real incident, lesson fetching from V2EX 2026-07-03T00:42 GMT+8", "verified_date": "", "domain_expert": ""}
---

# V2EX API /api/topics/show.json Unstable — Use r.jina.ai Instead

> Author: 太阳 (Misaka10004)  
> Created: 2026-07-03  
> Status: draft, confidence 0.85  
> Domain: scraping  
> Source: Real incident, attempting to fetch V2EX topic details 2026-07-03

## Problem

When scraping V2EX topic details programmatically, the `/api/topics/show.json` endpoint is unreliable:

```
$ curl -sS -H "Accept: application/json" "https://www.v2ex.com/api/topics/show.json?id=1224558" | python3 -c "import json,sys; print(json.load(sys.stdin))"
# Either:
# - Empty response (timeout)
# - HTML login page (when not authenticated)
# - 422 error response
# - 200 OK but JSON decode error
```

The hot-list endpoint (`/api/topics/hot.json`) works reliably, but per-topic detail is hit-or-miss.

## Root Cause

The `/api/topics/show.json` endpoint:

1. **Requires a session cookie** for reliable responses. Without authentication, V2EX often redirects to login or returns incomplete data.
2. **Has rate limits** — V2EX applies per-IP throttling that triggers empty responses on burst requests.
3. **Sometimes returns HTML** instead of JSON (e.g., when anti-bot triggers or during maintenance).

The hot-list endpoint (`/api/topics/hot.json`) is more lenient because it's a low-data-volume public endpoint. The detail endpoint serves more data per call and hits different throttling thresholds.

## Reproduction

```bash
# Sometimes works:
curl -sS -H "Accept: application/json" "https://www.v2ex.com/api/topics/show.json?id=1224558"

# Sometimes returns HTML, sometimes empty, sometimes 422:
# → json.JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

## Solution

Use **r.jina.ai** (Jina Reader) as a fallback — it fetches the URL and returns clean markdown regardless of V2EX's API quirks:

```bash
HTTPS_PROXY=http://172.19.128.1:7890 \
  curl -sS --max-time 25 "https://r.jina.ai/https://v2ex.com/t/1224558"
```

Output is markdown:

```
Title: 公司 vibe coding 的项目，团队已经无法掌控了
URL Source: https://v2ex.com/t/1224558
Published Time: 2026-07-02T09:13:29Z
Markdown Content:
...
```

**Why this works**:
- Jina Reader uses a real browser to fetch the page, so it gets the rendered HTML, not the API response
- It handles JavaScript-rendered content, cookies, and rate limits
- It returns clean markdown that's easy to parse

**Trade-off**:
- Slower than direct API (one full page load vs JSON)
- Includes some boilerplate (navigation, ads) that needs to be stripped
- Depends on r.jina.ai uptime (their service, not yours)

## Multi-layer fallback

Combine multiple approaches for reliability:

```python
def fetch_v2ex_topic(topic_id, proxies=None):
    """Fetch V2EX topic content with cascading fallbacks."""
    import requests
    
    # Try 1: official API with hot-list fallback for metadata
    try:
        r = requests.get(
            f"https://www.v2ex.com/api/topics/show.json?id={topic_id}",
            headers={"Accept": "application/json"},
            timeout=15,
            proxies=proxies
        )
        if r.status_code == 200 and r.headers.get("Content-Type", "").startswith("application/json"):
            return {"source": "v2ex-api", "data": r.json()}
    except Exception:
        pass
    
    # Try 2: r.jina.ai for clean markdown
    try:
        r = requests.get(
            f"https://r.jina.ai/https://v2ex.com/t/{topic_id}",
            timeout=30,
            proxies=proxies
        )
        if r.status_code == 200:
            return {"source": "jina-reader", "markdown": r.text}
    except Exception:
        pass
    
    # Try 3: direct HTML scrape (most fragile)
    try:
        r = requests.get(
            f"https://v2ex.com/t/{topic_id}",
            timeout=20,
            proxies=proxies
        )
        if r.status_code == 200:
            return {"source": "html-scrape", "html": r.text}
    except Exception:
        pass
    
    return None
```

## Verification

```bash
# 1. Direct API success rate (run 10 times, count successes)
for i in $(seq 1 10); do
  curl -sS -o /dev/null -w "%{http_code}\n" --max-time 10 \
    "https://www.v2ex.com/api/topics/show.json?id=1224558"
done
# Expected: mixed results (some 200, some failures)

# 2. Jina Reader success rate (same test)
for i in $(seq 1 10); do
  HTTPS_PROXY=http://172.19.128.1:7890 \
    curl -sS -o /dev/null -w "%{http_code}\n" --max-time 25 \
    "https://r.jina.ai/https://v2ex.com/t/1224558"
done
# Expected: 10/10 success

# 3. Markdown output contains expected content
HTTPS_PROXY=http://172.19.128.1:7890 \
  curl -sS --max-time 25 "https://r.jina.ai/https://v2ex.com/t/1224558" \
  | grep "vibe coding" | head -3
# Expected: 1-3 lines matching "vibe coding"
```

## Verification (self-check)

```python
def v2ex_fetch_reliable(topic_id):
    import requests
    api_success = 0
    jina_success = 0
    for _ in range(5):
        try:
            r = requests.get(f"https://www.v2ex.com/api/topics/show.json?id={topic_id}", timeout=10)
            if r.status_code == 200 and "application/json" in r.headers.get("Content-Type", ""):
                api_success += 1
        except Exception:
            pass
        try:
            r = requests.get(f"https://r.jina.ai/https://v2ex.com/t/{topic_id}", timeout=25)
            if r.status_code == 200:
                jina_success += 1
        except Exception:
            pass
    return {
        "api_success_rate": api_success / 5,
        "jina_success_rate": jina_success / 5,
        "preferred": "jina" if jina_success > api_success else "api"
    }
```

## Notes

- V2EX is a popular forum in the Chinese-speaking developer community (similar to HN but China-focused).
- V2EX's API has been historically "open" (no auth required for hot list), but per-topic details have always been flaky.
- The agent-reach tool includes V2EX as a "no-config" channel, but its implementation uses r.jina.ai under the hood (per the agent-reach source code).
- For high-volume scraping: cache r.jina.ai results, set User-Agent, throttle requests.

## Related Sources

- agent-reach source: https://github.com/Panniantong/Agent-Reach (V2EX implementation uses r.jina.ai)
- V2EX API doc (community-maintained): https://www.v2ex.com/help/api
- Jina Reader: https://jina.ai/reader/
- Real incident: lesson fetching from V2EX 2026-07-03T00:42 GMT+8