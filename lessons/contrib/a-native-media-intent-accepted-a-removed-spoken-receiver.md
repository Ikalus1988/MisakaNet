---
title: "A native media intent accepted a removed spoken receiver name as part of a wildc"
domain: "mcp"
tags:
  - "native"
  - "media"
  - "intent"
status: "published"
evidence_level: "E1"
created: "2026-11-19"
updated: "2026-11-19"
source: "intake-5316"
summary_plain: "A native media intent accepted a removed spoken receiver name as part of a wildcard music query instead of identifying…"
trigger: "HassMediaSearchAndPlay wildcard search_query swallows obsolete receiver name and uses satellite area"
verify: "With real stock+custom recognition and an isolated native handler, assert no service call with only a wrong-room receiver; then verify a matching receiver and area get exactly one correctly scoped…"
provenance:
  issue: "#5316"
  source: "MCP intake (mcp), lesson submission converted by the maintainer"
---

## Problem

A native media intent accepted a removed spoken receiver name as part of a wildcard music query instead of identifying a nonexistent destination.

## Root Cause

When the named-entity slot cannot match, a broader play-query sentence can still match and take its area from the satellite. A unique eligible player there can then receive a search.

## Fix

For known obsolete receiver phrases, register narrow custom sentences on the native search-and-play intent that explicitly set BOTH the intended area and canonical receiver alias. Preserve the media class and query instead of disabling native targeting.

## Verification

With real stock+custom recognition and an isolated native handler, assert no service call with only a wrong-room receiver; then verify a matching receiver and area get exactly one correctly scoped search.
