---
title: "An overlapping generic announcement sentence consumed the destination prefix and"
domain: "mcp"
tags:
  - "an"
  - "overlapping"
  - "generic"
status: "published"
evidence_level: "E1"
created: "2026-11-20"
updated: "2026-11-20"
source: "intake-5395"
summary_plain: "An overlapping generic announcement sentence consumed the destination prefix and sent it to the selected speaker as…"
trigger: "Hassil Home Assistant conversation trigger wildcard captures explicit speaker destination as announcement text"
verify: "Run real native recognition and the automation against a silent transport; assert exactly one expected body, no transport calls on empty/negated requests, and unchanged routes."
provenance:
  issue: "#5395"
  source: "MCP intake (codex), lesson submission converted by the maintainer"
---

## Problem

An overlapping generic announcement sentence consumed the destination prefix and sent it to the selected speaker as part of the announcement.

## Root Cause

The registered generic wildcard matched before the more-specific destination sentence. Reordering alone left destination-only phrases eligible for the generic wildcard.

## Fix

Register the explicit destination and its no-body literal ahead of the generic wildcard. Return a local clarification without invoking delivery when no message is present. Keep legitimate leading prepositions and repeated words inside the actual body.

## Verification

Run real native recognition and the automation against a silent transport; assert exactly one expected body, no transport calls on empty/negated requests, and unchanged routes.
