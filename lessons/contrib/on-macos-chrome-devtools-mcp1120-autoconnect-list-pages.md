---
title: "On macOS, chrome-devtools-mcp1.12.0 autoConnect list_pages timed out while the n"
domain: "development"
tags:
  - "on"
  - "macos"
  - "chrome"
status: "published"
evidence_level: "E1"
public_analogue: "chrome-devtools-mcp (the public npm package) and its list_pages tool"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4473"
summary_plain: "On macOS, chrome-devtools-mcp1.12.0 autoConnect list_pages timed out while the normal Chrome process still owned the…"
trigger: "On macOS, chrome-devtools-mcp1.12.0 autoConnect list_pages timed out while the n. On macOS, chrome-devtools-mcp1.12.0 autoConnect list_pages timed out while…"
verify: "After user unlock the locked flag disappeared, the same daemon logged Connected Puppeteer, normal Chrome exposed a window, and list_pages completed in2.95s with isError=false and five pages. No…"
provenance:
  issue: "#4473"
  source: "MCP intake (codex), lesson submission converted by the maintainer"
---

## Problem

On macOS, chrome-devtools-mcp1.12.0 autoConnect list_pages timed out while the normal Chrome process still owned the matching loopback debugging port. A short25s outer timeout initially obscured the actual60s server timeout; no current Allow prompt was observed.

## Root Cause

The active console was locked: read-only IORegistry metadata showed CGSSessionScreenIsLocked=true and kCGSSessionOnConsoleKey=true, while OS accessibility exposed zero Chrome windows. A private non-CDP-debug daemon log reached Connecting Puppeteer but not Connected Puppeteer. This case required console unlock, not package upgrade or a guessed new permission.

## Fix

Preserve the normal Chrome profile and credentials. Confirm process/port ownership and inspect only screen-lock flags. Use one sole maintained daemon and caller budget exceeding the server timeout; avoid concurrent retries. Ask the user to unlock the actual console, never bypass its lock. After unlock retry the original browser operation and resolve only after success.

## Verification

After user unlock the locked flag disappeared, the same daemon logged Connected Puppeteer, normal Chrome exposed a window, and list_pages completed in2.95s with isError=false and five pages. No browser restart after unlock or cookie/auth modifications were needed. Do not generalize every timeout to screen lock: require matching metadata and connection-stage evidence.
