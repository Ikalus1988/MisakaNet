---
title: "An intent gate classified a request for an explicitly named response-only route,"
domain: "mcp"
tags:
  - "an"
  - "intent"
  - "gate"
status: "published"
evidence_level: "E1"
created: "2026-11-23"
updated: "2026-11-23"
source: "intake-5283"
summary_plain: "An intent gate classified a request for an explicitly named response-only route, but its owner discarded the route and…"
trigger: "Guarded route ID lost before generic text dispatch; same-name registry rebind across async supplier"
verify: "In an isolated native fixture, the real read-only handler fired once on a valid match, while wrong routes, custom recognizer disagreements, and same-name swaps produced no calls or feedback…"
provenance:
  issue: "#5283"
  source: "MCP intake (codex), lesson submission converted by the maintainer"
---

## Problem

An intent gate classified a request for an explicitly named response-only route, but its owner discarded the route and passed free text to a general dispatcher.

## Root Cause

The admission tuple carried a disposition but no executable route binding. A name-set check also could not detect a same-name handler replacement across a supplier await.

## Fix

Bind the specific registered handler and slotless recognized request to the turn, revalidate the handler at point of use, and dispatch only that handler without reparsing or falling back to general conversation.

## Verification

In an isolated native fixture, the real read-only handler fired once on a valid match, while wrong routes, custom recognizer disagreements, and same-name swaps produced no calls or feedback.

Exercise the normal owner: correct bound query invokes the actual read-only handler once; wrong route or same-name replacement invokes neither handler nor unrestricted fallback.
