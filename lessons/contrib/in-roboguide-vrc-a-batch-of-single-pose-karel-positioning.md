---
title: "In ROBOGUIDE VRC, a batch of single-pose KAREL positioning programs (MO"
domain: "fanuc"
tags:
  - "in"
  - "roboguide"
  - "vrc"
status: "published"
evidence_level: "E1"
created: "2026-11-25"
updated: "2026-11-25"
source: "intake-5814"
summary_plain: "Symptom: In ROBOGUIDE VRC, a batch of single-pose KAREL positioning programs (MOVE TO target, then DELAY for hold)…"
trigger: "INTP-313 Motion statement failed KAREL MOVE TO after DELAY"
verify: "With DELAY in the template: first pose lands, next 10+ poses all fail with INTP-313 (motion statement failed in logfile, readback unchanged). After removing the DELAY line (recompiled, same…"
provenance:
  issue: "#5814"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

Symptom: In ROBOGUIDE VRC, a batch of single-pose KAREL positioning programs (MOVE TO target, then DELAY for hold) runs the first program fine, then EVERY subsequent program's MOVE TO is refused with `INTP-313 (prog, line) Motion statement failed`. The Run call returns success, the robot never moves, and re-firing the same program does not help (looks like swallowed motion commands but is not).

## Root Cause

VRC's KAREL DELAY never returns, so the first program stays hung at DELAY and keeps holding the motion group. Every later program starts, reaches MOVE TO, and the interpreter rejects it (INTP-31x family = motion lock / group occupied). Single-variable A/B on the same controller: only difference is the DELAY line.

## Fix

Do not use DELAY for pose-hold in sampling/positioning programs: end the program right after the motion (MOVE + marker WRITE + END). The robot naturally stays at the target after program end and the motion group is released immediately. If a hung DELAY task already exists, reboot the controller to clear it.

## Verification

With DELAY in the template: first pose lands, next 10+ poses all fail with INTP-313 (motion statement failed in logfile, readback unchanged). After removing the DELAY line (recompiled, same controller): the next single-pose run arrives in ~1s with readback matching the target joints exactly.

A/B: pose program with DELAY → next program's MOVE TO logs INTP-313 and robot stays put; same program without DELAY → next run arrives (readback joints == target within 0.005 deg).
