---
title: "An offline Home Assistant Apple TV player can still list apps. Using that list a"
domain: "mcp"
tags:
  - "an"
  - "offline"
  - "home"
status: "published"
evidence_level: "E1"
created: "2026-11-23"
updated: "2026-11-23"
source: "intake-5409"
summary_plain: "An offline Home Assistant Apple TV player can still list apps."
trigger: "Apple TV AppleTvMediaPlayer stale source_list after disconnect missing SELECT_SOURCE supported_features Home Assistant"
verify: "An integration fixture with a cached app list but missing SELECT_SOURCE issues zero setup/launch calls. Restoring the feature and returning one exact name produces one simulated source-selection call."
provenance:
  issue: "#5409"
  source: "MCP intake (codex), lesson submission converted by the maintainer"
---

## Problem

An offline Home Assistant Apple TV player can still list apps. Using that list as a readiness check allowed an automation to start switching other AV equipment before discovering that the player could not launch an app.

## Root Cause

The integration can retain its upstream application list on disconnect while dropping its source-selection capability. Neither an off state nor a nonempty cached list gives the full answer.

## Fix

Before acting, require an available non-restored player, a valid nonnegative integer supported_features containing SELECT_SOURCE, and exactly one advertised name. Recheck just before dispatch. Return listed or requested, not proof of picture or playback.

## Verification

An integration fixture with a cached app list but missing SELECT_SOURCE issues zero setup/launch calls. Restoring the feature and returning one exact name produces one simulated source-selection call.
