---
title: "A scheduling grammar with an unrestricted task wildcard before a date can match"
domain: "mcp"
tags:
  - "scheduling"
  - "grammar"
  - "an"
status: "published"
evidence_level: "E1"
created: "2026-11-19"
updated: "2026-11-19"
source: "intake-5308"
summary_plain: "A scheduling grammar with an unrestricted task wildcard before a date can match the last date in a sentence even when…"
trigger: "Hassil wildcard schedules an explicitly negated or competing reminder deadline"
verify: "Run the installed strict matcher and actual handler with a service spy. Competing or rejected deadlines must yield zero writes; positive controls must preserve the exact due instant and message."
provenance:
  issue: "#5308"
  source: "MCP intake (codex), lesson submission converted by the maintainer"
---

## Problem

A scheduling grammar with an unrestricted task wildcard before a date can match the last date in a sentence even when the speaker explicitly rejects that date.

## Root Cause

The matcher can consume the initial deadline and connecting negation as free task text; a valid final date and clock then look like the sole schedule. A service success does not validate the intended interpretation.

## Fix

Bind the full named deadline before the free-form task, or place it before the command that introduces the task. Where an existing duration-at-end route is retained, use a more-specific speech-only clarification for explicit competing and negated alternatives. Check the installed full matcher rather than assuming YAML order decides priority.

## Verification

Run the installed strict matcher and actual handler with a service spy. Competing or rejected deadlines must yield zero writes; positive controls must preserve the exact due instant and message.
