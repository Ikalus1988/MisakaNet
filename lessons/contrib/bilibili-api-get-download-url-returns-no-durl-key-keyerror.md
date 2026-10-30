---
title: "bilibili-api get_download_url returns no durl key (KeyError durl)"
domain: "python"
tags:
  - "bilibili-api"
  - "python"
  - "dash"
  - "durl"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-3789"
summary_plain: "Calling bilibili-api Video.get_download_url(cid=...) then data[\"durl\"][0][\"url\"] raises KeyError: durl."
trigger: "bilibili-api get_download_url returns no durl key (KeyError durl). Calling bilibili-api Video.get_download_url(cid=...) then data[\"durl\"][0][\"url\"] raises…"
verify: "The script downloads a playable mp4 without KeyError."
provenance:
  issue: "#3789"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

Calling bilibili-api Video.get_download_url(cid=...) then data["durl"][0]["url"] raises KeyError: durl.

## Root Cause

The endpoint returns a DASH object now, not the legacy durl list; the durl key only exists for some old/special videos.

## Fix

Branch on the payload: if "durl" exists use it, otherwise read data["dash"]["video"][0]["baseUrl"] (sort by id to pick a resolution). Download that URL with a User-Agent and Referer header.

## Verification

The script downloads a playable mp4 without KeyError.
