---
{
  "title": "Fault-tolerance for static pages calling external APIs",
  "domain": "frontend",
  "tags": ["api", "rate-limit", "static-site", "error-handling", "fault-tolerance", "github"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "translated_from": "lessons/contrib/static-page-github-api-403-rate-limit.md",
  "created": "2026-07-20",
  "updated": "2026-07-20"
}
---

# Fault-tolerance for static pages calling external APIs

> English translation / rewrite of `lessons/contrib/static-page-github-api-403-rate-limit.md`

## Problem

Pure static pages (HTML+JS on CDN/GitHub Pages, no backend) call third-party APIs from the browser. Risks:

- Hard rate limits (e.g. GitHub REST unauthenticated **60 req/hour**)
- `fetch` with no timeout hangs forever on bad networks
- One failed call kills unrelated UI via a shared `Promise.all` / try-catch
- No server-side key, cache, or request coalescing

## Design principles

### 1. Every external request needs a timeout

```js
async function fetchWithTimeout(url, timeoutMs = 8000) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const r = await fetch(url, { signal: ctrl.signal });
    clearTimeout(timer);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  } catch (e) {
    clearTimeout(timer);
    throw e;
  }
}
```

### 2. Parallel requests fail independently

```js
const [dataA, dataB] = await Promise.all([
  fetchWithTimeout(urlA).catch(() => null),
  fetchWithTimeout(urlB).catch(() => null),
]);
```

### 3. Features load independently

```js
// bad: one throw blocks the rest
// good:
loadA().catch(() => {});
loadB().catch(() => {});
loadC().catch(() => {});
```

### 4. Friendly degradation

Do not dump raw `TypeError: Failed to fetch` or `HTTP 403` to end users. Map abort → timeout message, 403 → rate-limit / auth message, network → retry later.

### 5. Prefer authenticated or cached paths when possible

For GitHub data on static sites: build-time fetch, or a tiny proxy, beats browser-anonymous spam against the 60/hour ceiling.

## Verification

- Kill network mid-load: page still shows other widgets
- Force 403: UI shows a calm fallback, not a blank page
- Confirm timeouts fire under ~timeoutMs
