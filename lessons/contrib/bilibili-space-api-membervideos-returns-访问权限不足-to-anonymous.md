---
title: "Bilibili space API (member/videos) returns 访问权限不足 to anonymous clients that have no wbi signature"
domain: "development"
tags:
  - "bilibili"
  - "wbi"
  - "api"
  - "risk-control"
  - "unsigned-endpoint"
  - "scraping"
status: "published"
evidence_level: "E1"
created: "2026-10-31"
updated: "2026-10-31"
source: "intake-4192"
summary_plain: "GET https://api.bilibili.com/x/space/wbi/arc/search?mid=<mid>&ps=5 without a signed query returned…"
trigger: "Bilibili space API (member/videos) returns 访问权限不足 to anonymous clients that have no wbi signature. GET…"
verify: "Anonymous GET of the popular endpoint should return `{\"code\":0,\"data\":{\"list\":[...]}}` with a non-empty list; a codes -352/-799/access-denied response from the space endpoint is the signature of the…"
provenance:
  issue: "#4192"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

GET https://api.bilibili.com/x/space/wbi/arc/search?mid=<mid>&ps=5 without a signed query returned `{"code":-352,"message":"风控校验失败"}` style rejection, and the older https://api.bilibili.com/x/space/arc/search?mid=<mid> answered `{"code":-799,"message":"请求过于频繁，请稍后再试"}` then `访问权限不足` — while the hot list https://api.bilibili.com/x/web-interface/popular?ps=20&pn=1 returned 200 with real data from the same machine, same UA and same minute. Observed 2026-10-31.

## Root Cause

Since 2023 the space endpoints require the wbi signature: a per-session mixin key derived from https://api.bilibili.com/x/web-interface/nav (img_url/sub_url), plus wts/rid and the per-request params, sorted and MD5-hashed. The hot list is a different, unsigned endpoint, which is why it works anonymously. The error text is misleading — it says access denied/frequency limited when the real cause is a missing signature.

## Fix

Two clean options:
1. Use an unsigned endpoint for public data: `https://api.bilibili.com/x/web-interface/popular?ps=N&pn=1` (hot list) with a browser User-Agent and `Referer: https://www.bilibili.com/`. Parse interactions (like/comment/share) and divide by view count to get rates instead of raw counts.
2. If per-creator data is really needed, implement wbi: fetch nav for img_key/sub_key, build `mixin_key = md5(img_key+sub_key)[:32]` with the reorder table, then sign `wts`-stamped params; without a logged-in cookie the result is still rate-limited aggressively.Do not retry the space endpoint in a loop: it escalates the risk-control block.

## Verification

Anonymous GET of the popular endpoint should return `{"code":0,"data":{"list":[...]}}` with a non-empty list; a codes -352/-799/access-denied response from the space endpoint is the signature of the missing wbi signature, not of a banned IP.
