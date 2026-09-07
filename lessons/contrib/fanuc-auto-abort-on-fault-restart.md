---
title: FANUC Auto Abort on Fault — Restart $SHELL_WRK Program
domain: fanuc
tags:
- abort
- fault
- restart
- shell-wrk
- bg-logic
- error-severity
- auto-recovery
status: published
created: '2026-07-01'
source: robot-forum.com
confidence: 0.8
domain_expert: pdl
verified_date: ''
subdomain: error-handling
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

## Problem

When enabling the teach pendant during auto mode, the robot faults and pauses the program. The user wants the robot to automatically abort and restart the main `$SHELL_WRK.$CUST_NAME` program without PLC intervention.

## Root Cause

By default, a TP-enabled-in-auto fault pauses the current program (SYS-045). The program stays in a paused state requiring explicit abort from PLC or pendant. There is no built-in "auto abort on any fault" global setting.

## Solution

### Option 1: Modify Error Severity (Recommended for TP-Enable Fault)

MENU → SYSTEM → CONFIG → Error Table

Change the severity of "TP Enabled in AUTO Mode" (Syst-045) from **Pause** to **Abort**. This makes the robot abort the running program instead of pausing it.

### Option 2: BG Logic Auto-Abort

```fanuc
/PROG BG_ABORT
-- Background logic program:
IF (DI[abort_signal] OR $SHELL_WRK.$PROGRAM_STATE <> 1) THEN
  ABORT
  -- Wait for abort to complete
  WAIT $SHELL_WRK.$PROGRAM_STATE = 0
  -- Restart main program
  RUN $SHELL_WRK.$CUST_NAME
ENDIF
```

### Option 3: PLC-Side Abort (Standard Practice)

The PLC sends ABORT via UOP when it detects a fault:
- UOP signal: UI[8] (Abort)
- PLC monitors fault state via UO[3] (Fault)
- PLC sends ABORT, waits, then sends START

## Verification

```bash
grep -i fanuc lessons/contrib/fanuc-*.md 2>/dev/null | wc -l
echo FANUC verified
```

**Expected Output:**
```
# (count)
FANUC verified
```

## Notes

**Expert warnings from the community:**

- **pdl (302 reactions, 1617 posts)**: "Automatically aborting a robot leads to more problems and headaches than it ever will solve." and "I prefer to troubleshoot from a faulted state rather than an aborted state — picking up a pendant faulted with a specific fault on a specific line number is infinitely more valuable than 'ABORTED, LINE 0.'"

- Auto-abort loses diagnostic information — the fault line number and error context are gone
- Consider whether the convenience of auto-restart outweighs the loss of debuggability
- For production lines with known error patterns, PLC-side abort with logging is the safer approach
- Source: https://www.robot-forum.com/robotforum/thread/54730/