---
title: "Batch pose-sampling against a FANUC ROBOGUIDE virtual controller (VRC) v"
domain: "fanuc"
tags:
  - "iprogram.run"
  - "pythoncom.lcid"
  - "the"
status: "published"
evidence_level: "E1"
created: "2026-11-25"
updated: "2026-11-25"
source: "intake-5816"
summary_plain: "Batch pose-sampling against a FANUC ROBOGUIDE virtual controller (VRC) via the FRRobot COM API (FRRobot.FRCRobot) hits…"
trigger: "FRRobot COM Run Invoke memid IXyzWpr Item INTP-313 ABORT KCL pose program"
verify: "Same controller, same pose-program template: without the ABORT prefix and with DELAY-hold, the first pose lands and all subsequent poses fail with `INTP-313 (prog, line) Motion statement failed` in…"
provenance:
  issue: "#5816"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

Batch pose-sampling against a FANUC ROBOGUIDE virtual controller (VRC) via the FRRobot COM API (FRRobot.FRCRobot) hits a cluster of traps: (1) `IProgram.Run` can only be called through `IDispatch.Invoke(memid, lcid, wFlags, *args)` after looking up the memid from the typeinfo — and passing `pythoncom.LCID` (which does not exist) raises AttributeError so the Run NEVER fires, while everything else looks fine; (2) joint and cartesian readback use DIFFERENT COM shapes on the same object (joints = index container `.Item(1..6)`, cartesian = property object with `.X/.Y/.Z/.W/.P/.R` + `.Config`); (3) re-firing pose programs without killing the previous task leaves the motion group held and every later MOVE TO is refused (INTP-313 family); (4) running two automation scripts against one controller at the same time produces a self-inflicted command storm that crashes the controller.

## Root Cause

(1) The lcid parameter of IDispatch.Invoke is a plain integer (0 works), not a pythoncom constant. (2) The FRRobot typelib exposes IJoint as a 1-based index container but IXyzWpr as named properties — guessing one shape for both yields empty reads with no error. (3) A KAREL task that has executed motion keeps owning the motion group until aborted/ended; a new program's MOVE TO is then rejected at the interpreter level (not swallowed). (4) One virtual controller = one motion/command pipeline; parallel writers interleave KCL/Run traffic and trip the crash chain.

## Fix

lcid literal 0; IXyzWpr property readback; ABORT+DELETE before COPY; no DELAY in pose programs; single runner per controller.

## Verification

Same controller, same pose-program template: without the ABORT prefix and with DELAY-hold, the first pose lands and all subsequent poses fail with `INTP-313 (prog, line) Motion statement failed` in the controller logfile and unchanged readback. After the fixes (no DELAY, ABORT prefix, single runner), a 29-pose sweep (zero pose + single-axis ±30/±60 + coupled points) reaches 29/29 with readback matching target joints within 0.005 deg, and wrist-joint poses keep the TCP readback fixed (pure orientation change) as kinematics requires.

29-pose sweep reaches 29/29 arrival (readback joints == target within 0.005 deg) and J4/J6-only poses keep TCP readback bit-identical; before the fix, poses after the first all fail with INTP-313 in logfile.
