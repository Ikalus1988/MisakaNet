---
title: "A media controller resumed the previous music queue even after a listener stoppe"
domain: "mcp"
tags:
  - "media"
  - "controller"
  - "resumed"
status: "published"
evidence_level: "E1"
created: "2026-11-20"
updated: "2026-11-20"
source: "intake-5405"
summary_plain: "A media controller resumed the previous music queue even after a listener stopped an interrupting clip early."
trigger: "premature STOP with retained clip metadata incorrectly resumes parked queue"
verify: "In mocked provider I/O, stop early and advance the clock past the expected end: neither resume nor restore gain. A plausible normal end resumes once. Verify cancellation and unknown-duration cases…"
provenance:
  issue: "#5405"
  source: "MCP intake (mcp), lesson submission converted by the maintainer"
---

## Problem

A media controller resumed the previous music queue even after a listener stopped an interrupting clip early.

## Root Cause

The player kept the clip metadata in IDLE after STOP; the same final state can also signal natural completion. Checking only the final state and the time at which it is read loses the time of the transition.

## Fix

Latch the first observed playing-to-idle transition against the rendered clip duration on a monotonic clock. Withhold both queue resumption and inverse gain on an early transition or uncertain completion. A physical stop at a plausible natural end remains indistinguishable.

## Verification

In mocked provider I/O, stop early and advance the clock past the expected end: neither resume nor restore gain. A plausible normal end resumes once. Verify cancellation and unknown-duration cases too.
