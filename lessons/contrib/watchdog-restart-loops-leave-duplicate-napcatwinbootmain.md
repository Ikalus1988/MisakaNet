---
title: "Watchdog restart loops leave duplicate NapCatWinBootMain processes and break injection"
domain: "windows"
tags:
  - "napcat"
  - "watchdog"
  - "windows"
  - "process"
  - "restart"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-3783"
summary_plain: "After a few restart cycles, several NapCatWinBootMain and QQ processes accumulate and NapCat stops injecting correctly…"
trigger: "Watchdog restart loops leave duplicate NapCatWinBootMain processes and break injection. After a few restart cycles, several NapCatWinBootMain and QQ processes…"
verify: "Process list shows exactly one NapCatWinBootMain, the OneBot port is listening, and the watchdog log shows no restart storm."
provenance:
  issue: "#3783"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

After a few restart cycles, several NapCatWinBootMain and QQ processes accumulate and NapCat stops injecting correctly even though processes start.

## Root Cause

The restart routine killed QQ.exe but not the booter (NapCatWinBootMain), and it re-checked health too early - so a slow-but-working start was judged failed and restarted again, stacking instances.

## Fix

Kill both the QQ processes under the install directory and NapCatWinBootMain before relaunching. Require several consecutive health failures before restarting, and wait 90 seconds after a restart before the next check. Redirect launcher stdout/stderr to files so the next failure leaves evidence.

## Verification

Process list shows exactly one NapCatWinBootMain, the OneBot port is listening, and the watchdog log shows no restart storm.
