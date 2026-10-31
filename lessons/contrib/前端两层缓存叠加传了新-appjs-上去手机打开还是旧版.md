---
title: "前端两层缓存叠加：传了新 app.js 上去，手机打开还是旧版"
domain: "devops"
tags:
  - "cloudflare"
  - "service-worker"
  - "cache"
  - "static-files"
  - "deployment"
  - "sw-version"
status: "published"
evidence_level: "E1"
created: "2026-10-31"
updated: "2026-10-31"
source: "intake-4156"
summary_plain: "新的 `app.js` 已经上传到服务器，手机打开网页还是旧逻辑，刷新、清缓存都不一定管用。"
trigger: "前端两层缓存叠加：传了新 app.js 上去，手机打开还是旧版. 新的 `app.js` 已经上传到服务器，手机打开网页还是旧逻辑，刷新、清缓存都不一定管用。"
verify: "`curl -sI https://.../app.js | grep -i cache-control` 显示 no-cache；手机强杀重开是新版本；DevTools → Application → Cache Storage 里出现新版本号。"
provenance:
  issue: "#4156"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

新的 `app.js` 已经上传到服务器，手机打开网页还是旧逻辑，刷新、清缓存都不一定管用。

## Root Cause

两层缓存叠在一起：
1. **Cloudflare**：`serveStatic` 只给 `.html` / `sw.js` 设了 `no-cache`，`.js` 是 `public, max-age=3600`，CF 实际会更久；
2. **Service Worker**：`sw.js` 里 `CACHE = 'bms-web-v1'` 写死，SW 文件本身不变就不会重新 `addAll(SHELL)`，旧资源一直从 Cache Storage 里拿。

## Fix

```js
// 1) noCache 覆盖前端三类
const noCache = /\.(html|js|css|webmanifest|sw\.js)$/i;

// 2) sw.js 里把版本号 +1（约定写进 README）
const CACHE = 'bms-web-v2';
```
以后改任何前端文件，先想一遍「sw.js 的 CACHE 要不要 +1」。

## Verification

`curl -sI https://.../app.js | grep -i cache-control` 显示 no-cache；手机强杀重开是新版本；DevTools → Application → Cache Storage 里出现新版本号。
