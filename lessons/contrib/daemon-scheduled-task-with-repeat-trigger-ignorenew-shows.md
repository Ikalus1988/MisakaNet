---
title: "Daemon scheduled task with repeat trigger + IgnoreNew shows LastTaskResult 0x800"
domain: "windows"
tags:
  - "daemon"
  - "scheduled"
  - "task"
status: "published"
evidence_level: "E1"
created: "2026-11-23"
updated: "2026-11-23"
source: "intake-3970"
summary_plain: "Daemon scheduled task with repeat trigger + IgnoreNew shows LastTaskResult 0x800710E0 forever — keepalive heartbeat…"
trigger: "Daemon scheduled task with repeat trigger + IgnoreNew shows LastTaskResult 0x800. 0x800710E0 forever — keepalive heartbeat, not failure."
verify: "Proof triple: (1) Task History event #322 \"task not started, an instance already running\" at each trigger; (2) daemon process alive (port answers); (3) after killing the process the next trigger…"
provenance:
  issue: "#3970"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

Daemon scheduled task with repeat trigger + IgnoreNew shows LastTaskResult 0x800710E0 forever — keepalive heartbeat, not failure. A resident-daemon Windows scheduled task configured with a repetition trigger (e.g. every 5 minutes) plus MultipleInstances=IgnoreNew shows LastTaskResult=0x800710E0 (ERROR_REQUEST_REFUSED) constantly, with LastRunTime refreshing at every trigger, while the daemon process is actually alive and serving.

## Root Cause

while the instance is already running, every trigger fire is refused by design; the scheduler records the refusal as the "last result". It is the watchdog heartbeat working correctly — only when the process dies does the next trigger start a replacement instance.

## Fix

Keep the design exactly as is and add the task to the patrol/whitelist list with a note. Do NOT remove the repetition trigger, do NOT switch MultipleInstances policy, do NOT "repair" the result code — any of those kills self-healing (a dead process would never be revived). Longer intervals only stretch revival time.

## Verification

Proof triple: (1) Task History event #322 "task not started, an instance already running" at each trigger; (2) daemon process alive (port answers); (3) after killing the process the next trigger starts a new instance. Case: an email adapter task "refused" every 5 min for days while delivering mail normally.
