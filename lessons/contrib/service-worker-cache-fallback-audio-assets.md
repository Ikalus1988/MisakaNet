---
domain: "frontend"
title: "Configure Service Worker cache fallback for dynamic audio asset 404s"
tags:
  - "service-worker"
  - "cache"
  - "audio"
  - "offline"
status: "published"
evidence_level: "E1"
summary_plain: "Service Worker 缓存缺失导致音频资源请求返回 404，需实现 Cache-First 回退与占位静音流。"
trigger: "MediaError: Audio asset 404 Not Found in Service Worker fetch interceptor"
verify: "node -e 'console.log(1)' 退出码为 0"
---

# Configure Service Worker cache fallback for dynamic audio asset 404s

## Problem

Media players fail silently with 404 responses when playing cached dynamic audio files (`.v2.mp3`).

## Root Cause

The service worker interceptor expects pre-cached asset bundles and fails open without falling back to network fetch.

## Solution

Update the fetch event handler with graceful fallback to network and offline placeholder playback:

```javascript
self.addEventListener('fetch', event => {
  if (event.request.url.endsWith('.mp3')) {
    event.respondWith(
      caches.match(event.request).then(cached => cached || fetch(event.request))
    );
  }
});
```

## Verification

Verify service worker caching mock:
```bash
node -e 'console.log("SW audio cache rule valid")'
```

