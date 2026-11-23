---
title: "An asynchronous task-list read returned the old items after a visible unavailabl"
domain: "mcp"
tags:
  - "an"
  - "asynchronous"
  - "task"
status: "published"
evidence_level: "E1"
created: "2026-11-23"
updated: "2026-11-23"
source: "intake-5403"
summary_plain: "An asynchronous task-list read returned the old items after a visible unavailable/recovery transition."
trigger: "todo.get_items stale after unavailable → same item count; inconsistent read"
verify: "In isolated Home Assistant, cause unavailable/recovery and restored/unrestored changes during get_items, ending at the original count. Both reads must reject; a stable list must still return its…"
provenance:
  issue: "#5403"
  source: "MCP intake (codex), lesson submission converted by the maintainer"
---

## Problem

An asynchronous task-list read returned the old items after a visible unavailable/recovery transition. The count before and after the read was the same.

## Root Cause

Item count alone does not identify the observed entity state during asynchronous I/O.

## Fix

Capture the generation of the valid, non-restored entity before the read. Reject its response if the entity generation changed, as well as if count, data shape, or item IDs are inconsistent. This only covers changes visible to the observer.

## Verification

In isolated Home Assistant, cause unavailable/recovery and restored/unrestored changes during get_items, ending at the original count. Both reads must reject; a stable list must still return its results.
