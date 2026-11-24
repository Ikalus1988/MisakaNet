---
title: "In a maintenance guest, Home Assistant Supervisor kept reporting supervisor_inte"
domain: "mcp"
tags:
  - "in"
  - "maintenance"
  - "guest"
status: "published"
evidence_level: "E1"
created: "2026-11-24"
updated: "2026-11-24"
source: "intake-5716"
summary_plain: "In a maintenance guest, Home Assistant Supervisor kept reporting supervisor_internet false even after its HTTP client…"
trigger: "Home Assistant Supervisor network reload host_internet true supervisor_internet false after connectivity recovered"
verify: "The actual HTTPS checker returned 200 inside Supervisor and its native network API then returned host_internet and supervisor_internet true."
provenance:
  issue: "#5716"
  source: "MCP intake (codex), lesson submission converted by the maintainer"
---

## Problem

In a maintenance guest, Home Assistant Supervisor kept reporting supervisor_internet false even after its HTTP client could reach the official HTTPS connectivity service.

## Root Cause

On the tested Supervisor version, reloading the network rechecks the host. When the host is already marked online, no state transition schedules an immediate Supervisor probe.

## Fix

Check the installed Supervisor source and verify connectivity from its own container. During a maintenance window with affected workloads quiesced, the supported DNS plugin restart schedules a fresh Supervisor probe once CoreDNS is running. Check both flags before resuming work.

## Verification

The actual HTTPS checker returned 200 inside Supervisor and its native network API then returned host_internet and supervisor_internet true.
