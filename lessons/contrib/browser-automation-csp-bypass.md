---
title: "CSP blocks JavaScript injection in browser automation of authenticated pages"
domain: "mcp"
tags: ["browser-automation", "csp", "content-security-policy", "cdp", "puppeteer", "playwright", "eval", "injection"]
status: "published"
source: "zsxh1990"
subdomain: "browser-automation"
confidence: "0.8"
created: "2026-07-06"
updated: "2026-07-06"
verified_date: "2026-07-06"
---

# CSP blocks JavaScript injection in browser automation of authenticated pages

## Problem

Browser automation tools (Puppeteer, Playwright, CDP-based tools) fail silently
when injecting JavaScript into pages with strict Content Security Policy headers.

Symptoms:
- `page.evaluate()` returns `null` or throws `EvalError`
- Injected scripts execute but have no visible effect
- `Runtime.evaluate` via CDP returns `{"result":{"type":"undefined"}}`
- The page works fine in manual browsing; only automation fails
- Some sites work on first load but fail after login (CSP set per-route)

Common CSP headers that cause this:

```
Content-Security-Policy: script-src 'self' 'nonce-abc123'
Content-Security-Policy: script-src 'self' 'sha256-...'
Content-Security-Policy: default-src 'self'; script-src 'self'
```

When `script-src` does not include `'unsafe-inline'` or `'unsafe-eval'`,
any dynamically injected script without a matching nonce or hash is blocked.

## Root Cause

Browser automation tools inject JavaScript in two ways:

1. **`eval()` / `Function()`**: Creates scripts from strings. Blocked by CSP unless `'unsafe-eval'` is allowed.
2. **Inline script injection**: Creates `<script>` elements with text content. Blocked by CSP unless `'unsafe-inline'` or a matching nonce is present.

Most production sites (banking, enterprise SaaS, government portals) use strict CSP
specifically to prevent XSS. This security measure also blocks legitimate automation.

The CSP check happens at the browser level, not the server level.
Even CDP (Chrome DevTools Protocol) respects CSP for `Runtime.evaluate`.

## Solution

### 1. Use CDP `Page.addScriptToEvaluateOnNewDocument` (recommended)

This method injects a script that runs before any page scripts, bypassing CSP
because it executes in the browser's privileged context:

```python
# CDP direct call — works even with strict CSP
await client.send("Page.addScriptToEvaluateOnNewDocument", {
    "source": """
        // This runs before CSP is applied
        window.__automationReady = true;
        window.__extractData = () => {
            return document.querySelector('.data-table')?.innerText;
        };
    """
})
await client.send("Page.navigate", {"url": target_url})
# After navigation, call window.__extractData() via Runtime.evaluate
```

**Why it works**: `addScriptToEvaluateOnNewDocument` injects at the browser level,
before the page's CSP header is parsed. The injected code becomes part of the
page's initial script context.

### 2. Use Chrome flags to disable CSP (development only)

```bash
# Launch Chrome with CSP disabled — NEVER use in production
chrome --disable-web-security --user-data-dir=/tmp/chrome-automation
```

Or via Puppeteer/Playwright:

```python
browser = await puppeteer.launch({
    args: ['--disable-web-security'],
    headless: true,
})
```

**Warning**: This disables ALL security protections, not just CSP.
Only use for testing on pages you control.

### 3. Extract data via DOM APIs instead of eval

When you only need to read data (not execute logic), use DOM traversal
which is not subject to CSP:

```python
# Instead of: page.evaluate("document.querySelector('.price').innerText")
# Use CDP DOM API directly:
result = await client.send("DOM.getDocument", {"depth": 3})
node_id = await client.send("DOM.querySelector", {
    "nodeId": result["root"]["nodeId"],
    "selector": ".price"
})
text = await client.send("DOM.getOuterHTML", {"nodeId": node_id["nodeId"]})
```

### 4. Use the page's own nonce (advanced)

Some pages expose their CSP nonce in a meta tag or global variable.
You can reuse it for injected scripts:

```python
nonce = await page.evaluate("""
    // Try to find the nonce from existing script tags
    document.querySelector('script[nonce]')?.nonce
    || document.querySelector('meta[http-equiv="Content-Security-Policy"]')
        ?.content?.match(/nonce-([a-zA-Z0-9+/=]+)/)?.[1]
""")

if nonce:
    await page.evaluate(f"""
        const script = document.createElement('script');
        script.nonce = '{nonce}';
        script.textContent = 'window.__extractData = () => document.body.innerText';
        document.head.appendChild(script);
    """)
```

## Verification

### Test 1: Detect CSP on target page

```bash
# Check if a page has CSP
curl -sI https://example.com | grep -i content-security-policy

# Or via CDP
python3 -c "
import asyncio, websockets, json
async def check():
    async with websockets.connect('ws://localhost:9222/devtools/page/...') as ws:
        await ws.send(json.dumps({'id': 1, 'method': 'Network.enable'}))
        # Listen for response with CSP header
asyncio.run(check())
"
```

### Test 2: Verify injection works with addScriptToEvaluateOnNewDocument

```python
import asyncio
from playwright.async_api import async_playwright

async def test_csp_bypass():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Inject before navigation
        await page.add_init_script("""
            window.__bypass = true;
            window.__getData = () => document.title;
        """)

        await page.goto("https://example.com")  # has strict CSP
        result = await page.evaluate("window.__bypass")
        assert result == True, "CSP bypass failed"
        print("CSP bypass works")

        await browser.close()

asyncio.run(test_csp_bypass())
```

Expected: `CSP bypass works` — confirms injection survives CSP.

### Test 3: Verify eval is blocked without bypass

```python
# This should fail on CSP-protected pages:
try:
    result = await page.evaluate("document.title")
    print(f"eval works: {result}")
except Exception as e:
    print(f"eval blocked by CSP: {e}")
```

Expected on strict-CSP pages: `eval blocked by CSP` or silent `null` return.

## Notes

- `addScriptToEvaluateOnNewDocument` is the most reliable bypass because it runs before CSP parsing. It works in headless Chrome, Chromium, and all Playwright/Puppeteer versions.
- CDP's `Runtime.evaluate` respects CSP. `Page.addScriptToEvaluateOnNewDocument` does not. This is by design — the latter is a browser-level injection, not a page-level eval.
- Some sites use CSP `report-uri` or `report-to` to log violations. Your automation may trigger violation reports even if the script executes successfully.
- For scraping authenticated pages, prefer reading cookies/session from the automation tool's context rather than injecting scripts to extract auth tokens.
- Related: `browser-harness-cdp-browser-automation.md` (CDP basics), `feishu-block-api-false-success.md` (API false success patterns).

## Environment

- Browsers: Chromium 120+, Chrome 120+, Firefox 120+ (partial CSP bypass support)
- Tools: Puppeteer 21+, Playwright 1.40+, raw CDP via WebSocket
- Platform: Linux, macOS, Windows
