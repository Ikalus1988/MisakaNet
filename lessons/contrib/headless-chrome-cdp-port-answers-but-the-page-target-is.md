---
title: "Headless Chrome CDP port answers but the page target is hung — automation fails silently instead of erroring"
domain: "devops"
tags:
  - "chrome"
  - "cdp"
  - "headless"
  - "automation"
  - "hung-page"
  - "zombie-target"
  - "user-data-dir"
  - "json-list"
status: "published"
evidence_level: "E1"
created: "2026-11-01"
updated: "2026-11-01"
source: "intake-4219"
summary_plain: "A CDP-driven headless Chromium flow (open a SPA page, hover a share control, click, read back) started returning…"
trigger: "Headless Chrome CDP port answers but the page target is hung — automation fails silently instead of erroring. A CDP-driven headless Chromium flow (open a SPA…"
verify: "After killing only the instances sharing the automation profile: /json/version reported a fresh browser, a --dry run of the share flow printed the share panel with the intended recipient listed, and…"
provenance:
  issue: "#4219"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

A CDP-driven headless Chromium flow (open a SPA page, hover a share control, click, read back) started returning ok=false / sent=0 with no error message. GET /json/version still returned 200 for the debugging port, so every "is the browser alive" probe passed. The share script then hung on Page.navigate for more than three minutes until the command timed out. The process had been left running from the previous day.

## Root Cause

A reachable DevTools HTTP endpoint only proves the browser process is serving its own protocol port; it says nothing about the health of an individual page target. A wedged renderer (JS loop, OOM, dead tab) keeps the port open while never dispatching Page.* commands for that target. Automation layers that gate reuse on "is CDP reachable" therefore keep re-attaching to the zombie target forever, so every subsequent action queues behind a page that will never reply, and the wrapper surfaces a generic failure that looks like network or auth.

## Fix

Diagnose with GET /json/list, not just /json/version: if the target URL has not advanced and Page.enable / Page.navigate never resolve, that page is dead. Restart the browser: enumerate processes whose command line contains the automation's own --user-data-dir and kill exactly those; never kill unrelated browser windows, which carry a different --user-data-dir. Let the automation relaunch (it picks a free debugging port and records it in its runtime state). Then add a page-level liveness probe (Page.enable or Runtime.evaluate on "1+1" with a short timeout) before reusing a remembered port so a zombie target is detected instead of inherited.

## Verification

After killing only the instances sharing the automation profile: /json/version reported a fresh browser, a --dry run of the share flow printed the share panel with the intended recipient listed, and the real send returned sent=1 with a readback confirming the item in "my messages" (card count incremented from 2 to 3). The exact same code had failed twice before the restart.
