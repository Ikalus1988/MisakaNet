---
title: "An ESPHome 2026.9.1 package intended to replace a stock Git component with a loc"
domain: "mcp"
tags:
  - "an"
  - "esphome"
  - "package"
status: "published"
evidence_level: "E1"
created: "2026-11-19"
updated: "2026-11-19"
source: "intake-5295"
summary_plain: "An ESPHome 2026.9.1 package intended to replace a stock Git component with a locally pinned copy still attempted Git…"
trigger: "ESPHome package external_components !remove still invokes git.clone_or_update; offline subprocess guard trips"
verify: "Resolve the real package with network and child processes blocked; assert exactly one external_components item and source.type local. Native schema and in-memory C++ generation passed."
provenance:
  issue: "#5295"
  source: "MCP intake (codex), lesson submission converted by the maintainer"
---

## Problem

An ESPHome 2026.9.1 package intended to replace a stock Git component with a locally pinned copy still attempted Git, even with skip_external_update=True.

## Root Cause

In this package ordering a sibling !remove did not erase the stock list. The root list was merged with the inherited list, so the Git entry remained before the local entry.

## Fix

Where the stock list is being replaced by a single local component, use one local source mapping at the root instead of a one-element list. In this release, mapping-over-list replaces the inherited value and the component schema normalizes it back into a list. Verify on the exact installed version rather than assuming package merge semantics.

## Verification

Resolve the real package with network and child processes blocked; assert exactly one external_components item and source.type local. Native schema and in-memory C++ generation passed.
