{"title": "FANUC Auto Abort on Fault — Restart $SHELL_WRK Program", "domain": "fanuc", "subdomain": "error-handling", "tags": ["abort", "fault", "restart", "shell-wrk", "bg-logic", "error-severity", "auto-recovery"], "source": "robot-forum.com", "status": "published", "confidence": "0.8", "created": "2026-07-01", "verified_date": "", "domain_expert": "pdl"}


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

1. Run program in auto mode
2. Enable TP → robot should abort (not pause) if using Option 1
3. Check that $SHELL_WRK.$CUST_NAME can be restarted
4. Verify no lingering program state from the aborted program

## Notes

**Expert warnings from the community:**

- **pdl (302 reactions, 1617 posts)**: "Automatically aborting a robot leads to more problems and headaches than it ever will solve." and "I prefer to troubleshoot from a faulted state rather than an aborted state — picking up a pendant faulted with a specific fault on a specific line number is infinitely more valuable than 'ABORTED, LINE 0.'"

- Auto-abort loses diagnostic information — the fault line number and error context are gone
- Consider whether the convenience of auto-restart outweighs the loss of debuggability
- For production lines with known error patterns, PLC-side abort with logging is the safer approach
- Source: https://www.robot-forum.com/robotforum/thread/54730/
