---
title: "A mobile GPS update delivered late looked current to a Home Assistant arrival au"
domain: "mcp"
tags:
  - "mobile"
  - "gps"
  - "update"
status: "published"
evidence_level: "E1"
created: "2026-11-23"
updated: "2026-11-23"
source: "intake-5311"
summary_plain: "A mobile GPS update delivered late looked current to a Home Assistant arrival automation."
trigger: "Home Assistant mobile_app last_updated stale GPS delayed geofence arrival opens garage"
verify: "In isolated Core, a GPS-only point delivered after 25 minutes emits nothing; each order within 90 seconds qualifies once, and 91 seconds or a different device does not."
provenance:
  issue: "#5311"
  source: "MCP intake (codex), lesson submission converted by the maintainer"
---

## Problem

A mobile GPS update delivered late looked current to a Home Assistant arrival automation.

## Root Cause

A tracker’s last_updated describes receipt by Home Assistant, not a guaranteed sensor acquisition time. An older inbound point delivered well after the last outside point could finish a trip by itself.

## Fix

After corroborated departure, pair an accurate near point with a separately observed offsite-to-home network edge for that same device in either order within a fixed short window. Do not renew the first deadline on roaming or repeat fixes; missed returns are preferable to delayed actuation.

## Verification

In isolated Core, a GPS-only point delivered after 25 minutes emits nothing; each order within 90 seconds qualifies once, and 91 seconds or a different device does not.
