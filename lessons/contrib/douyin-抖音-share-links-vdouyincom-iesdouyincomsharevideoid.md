---
title: "Douyin (抖音) share links (v.douyin.com / iesdouyin.com/share/video/<id>) cannot b"
domain: "windows"
tags:
  - "douyin"
  - "share"
  - "links"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-5013"
summary_plain: "Douyin (抖音) share links (v.douyin.com / iesdouyin.com/share/video/<id>) cannot be resolved by any automated path on a…"
trigger: "Douyin (抖音) share links (v.douyin.com / iesdouyin.com/share/video/<id>) cannot b. be resolved by any automated path on a clean Windows machine (tested…"
verify: "yt-dlp with/without browser cookies: same error. CDP network capture of headless Edge: 0 video responses, verification interstitial in DOM. _ROUTER_DATA dump: no play_addr keys."
provenance:
  issue: "#5013"
  source: "MCP intake (other), lesson submission converted by the maintainer"
---

## Problem

Douyin (抖音) share links (v.douyin.com / iesdouyin.com/share/video/<id>) cannot be resolved by any automated path on a clean Windows machine (tested 2026-11-15, yt-dlp 2026.10.26).

Symptom: yt-dlp fails with "[Douyin] <id>: Fresh cookies (not necessarily logged in) are needed" even when a fresh browser cookie jar (ttwid + s_v_web_id + __ac_signature + __ac_nonce) is supplied via --cookies.

## Root Cause

1. yt-dlp DouyinIE (in tiktok.py) calls www.douyin.com/aweme/v1/web/aweme/detail/ without the JS-generated request signature (a_bogus); the API returns empty aweme_detail, and the extractor raises the "Fresh cookies" error. Its source has a TODO "Run verification challenge code to generate signature cookies" — cookies alone can never fix it.
2. The share page's window._ROUTER_DATA no longer embeds video data: loaderData["video_(id)/page"] has no videoInfoRes/item_list/play_addr (old scraping recipes are dead).
3. Rendering the share page in headless Edge (even with --disable-blink-features=AutomationControlled and a mobile UA) lands on a login-verification interstitial ("请在抖音 App 内观看"); no video request is ever made (verified via CDP Network.responseReceived — only security SDK/mssdk/zijieapi telemetry).
4. Anonymous ttwid can be obtained from ttwid.bytedance.com/ttwid/union/register/ (POST JSON body via --data-binary @file; PowerShell inline -d mangles quotes → {"status_code":1001,"message":"parse params fail"}), but it does not help DouyinIE.

## Fix

No reliable automated fix as of 2026-11. Workaround: have the user save the video in the Douyin app and send the file directly (local mp4 paths / direct CDN URLs work fine with yt-dlp generic + ffmpeg). For chatbot integrations, detect v.douyin.com|iesdouyin.com links and skip video tools instead of burning a turn on a guaranteed failure.

## Verification

yt-dlp with/without browser cookies: same error. CDP network capture of headless Edge: 0 video responses, verification interstitial in DOM. _ROUTER_DATA dump: no play_addr keys.
