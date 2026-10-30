---
title: "yt-dlp cannot download Bilibili video: Requested format is not available"
domain: "python"
tags:
  - "yt-dlp"
  - "bilibili"
  - "download"
  - "dash"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-3788"
summary_plain: "yt-dlp with a Bilibili URL exits with ERROR: Requested format is not available, even though the page loads and cookies…"
trigger: "yt-dlp cannot download Bilibili video: Requested format is not available. yt-dlp with a Bilibili URL exits with ERROR: Requested format is not available, even…"
verify: "yt-dlp downloads a file (video-only mp4 or m4a) without the format error."
provenance:
  issue: "#3788"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

yt-dlp with a Bilibili URL exits with ERROR: Requested format is not available, even though the page loads and cookies are supplied.

## Root Cause

Bilibili serves separate video-only and audio-only DASH streams plus premium-only tiers. Best/single-file format selectors match nothing for a non-premium account, and a header-based cookie is deprecated for authentication.

## Fix

For frame extraction request video-only: -f "bv*[height<=480]". For audio-only request an audio format id. Pass cookies with --cookies cookies.txt (Netscape format) instead of an added Cookie header.

## Verification

yt-dlp downloads a file (video-only mp4 or m4a) without the format error.
