---
title: "A checked-in Codex skill can exist without being available to the client. Root C"
domain: "mcp"
tags:
  - "checked"
  - "in"
  - "codex"
status: "published"
evidence_level: "E1"
created: "2026-11-23"
updated: "2026-11-23"
source: "intake-5497"
summary_plain: "A checked-in Codex skill can exist without being available to the client."
trigger: "Codex SKILL.md exists but missing description or disabled skill not discovered; skills/list forceReload repo identity"
verify: "In a temporary Git checkout, native skills/list must return a healthy skill enabled, a configured disabled skill disabled, and a missing-description skill absent with a loader error."
provenance:
  issue: "#5497"
  source: "MCP intake (codex), lesson submission converted by the maintainer"
---

## Problem

A checked-in Codex skill can exist without being available to the client.

## Root Cause

Filesystem presence, native parsing and per-home enablement are separate layers. A name-only lookup can also match a different scope.

## Fix

Initialize a fresh stdio app-server and request skills/list for the exact checkout with forceReload=true. Compare cwd, path, name, repo scope, enabled state and load errors. Report competing enabled names and scope foreign loader errors separately. No model turn or target skill execution is necessary. Repeat per checkout and home; this is not evidence of model task performance.

## Verification

In a temporary Git checkout, native skills/list must return a healthy skill enabled, a configured disabled skill disabled, and a missing-description skill absent with a loader error.
