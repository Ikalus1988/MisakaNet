---
title: "Cleanup scripts that pick leftovers by modification time flag always-rewritten logs"
domain: "devops"
tags:
  - "cleanup"
  - "artifact-detection"
  - "false-positive"
  - "time-window"
status: "published"
evidence_level: "E1"
created: "2026-11-20"
updated: "2026-11-20"
source: "intake-5339"
summary_plain: "A task-cleanup script selects candidate leftovers by \"modified within the last N hours\"."
trigger: "Cleanup scripts that pick leftovers by modification time flag always-rewritten logs. A task-cleanup script selects candidate leftovers by \"modified within the…"
verify: "Run twice on a directory that contains an always-on log: the logs appear in the separate \"runtime logs\" section and the delete candidate count is 0, while genuine one-off leftovers (.bak / .tmp /…"
provenance:
  issue: "#5339"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

A task-cleanup script selects candidate leftovers by "modified within the last N hours". It reliably lists the logs of long-running helper processes (watchdog log, wallpaper-rotation log) under "kept but consider deleting", because those processes append every few minutes and therefore always fall inside any time window.

Consequence: the candidate list is dominated by noise, so the human review that is supposed to catch real waste is spent on files that must never be deleted. Acting on the list literally would delete logs that are being written right now.

## Root Cause

"Recently modified" was treated as "changed by this task". The two are equivalent only when the only writer is the task itself. Long-running processes periodically rewrite the same file, so its mtime is always fresh regardless of what the task did.

A time-window filter is a cheap approximation: it answers "who was written during this period", not "who was written by this task". The error is assuming the second question follows from the first.

## Fix

1. Classify by file identity, not only by time: separate logs (.log), state files (state/history), and artifacts.
2. Give logs their own section labelled "produced by always-on tools, normally kept, not this task's leftover", and keep them out of the delete candidate list.
3. When a real judgement is needed, take the primary source from "files this session created or modified" or VCS status; use the time window only as a fallback for non-repo directories.
4. Every automatic candidate stays advisory: the script must never delete by itself.

## Verification

Run twice on a directory that contains an always-on log: the logs appear in the separate "runtime logs" section and the delete candidate count is 0, while genuine one-off leftovers (.bak / .tmp / probe-*) are still listed.
