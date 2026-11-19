---
title: "Accepted is not executed: measure readiness at the layer that will do the work"
domain: "fanuc"
tags:
  - "readiness"
  - "automation"
  - "controller"
  - "karel"
  - "motion"
status: "published"
evidence_level: "E1"
created: "2026-11-18"
updated: "2026-11-18"
source: "intake-5169"
summary_plain: "命令层起来了不代表运动层就绪：RUN 被接受却零位移、报 MCTL-003；端口身份还会漂移，探活要打到目标控制器本身。"
trigger: "accepted RUN but program aborted zero motion MCTL-003 system in error status INTP-313 KCL option not loaded during startup run protected"
verify: "After a restart, poll the signal produced by the layer you need (the copy command echoing its result, or a position probe). A success from another layer means the target layer is not ready."
provenance:
  issue: "#5169"
  source: "MCP intake (claude-code), contributor-reported"
---

## Problem

Two automations against the same kind of controller failed the same way: the command they sent was
**accepted**, and nothing happened.

* Injecting a compiled program: the copy step answered normally, the program appeared in the listing,
  and `RUN` came back refused or "protected" — while a `show` command on the same connection worked
  fine. The console's command table had `RUN` in a slot one position off from the documentation, so the
  "unlock" step cleared the wrong entry and the run stayed protected.
* Running a motion program: `RUN` was accepted, the program state said `ABORTED`, and the error log
  carried a motion-statement failure plus "system is in error status". Re-sending did nothing; the
  command layer answered every time. A second automation on the same controller hit the same shape
  from the injection side: copy and listing answered normally while `RUN` stayed refused.

## Root Cause

The controller has layers, and they come up at different times:

* During the first 30–45 s after a restart, the **command layer** answers (copy, show, set) while the
  **runtime** that executes programs is still initializing — the refusal reads like a missing license,
  and the license is demonstrably present in the log.
* A **motion** layer can be in a latched error state that blocks motion statements while accepting
  every command that is not motion. That is the trap: a green `RUN` in a loop that never moves.
* The command table is data, not documentation: a slot index taken from a document and never read
  back from the device will be wrong eventually.
* Template workcells are configured with **identical service ports**, so a health probe that asks the
  port listed in the workcell file can answer from a different controller — a false `HEALTHY` that is
  worse than a failure.

So "the command returned 0" is a statement about the command layer. Readiness has to be measured at the
layer that will do the work.

## Fix

Pick the readiness signal from the target layer, and treat the command layer's success as necessary
only:

```python
def wait_ready(ctl, timeout=120):
    # The copy step echoes its own result: that echo is the first point where the runtime is up.
    for _ in range(timeout // 3):
        if "Copied" in ctl.console("COPY UD1:PROBE.PC MD: OVERWRITE"):
            return True
        sleep(3)
    raise TimeoutError("runtime never reached the copy layer")

# Motion needs its own probe, not the command layer's success.
def motion_ready(ctl):
    ctl.reset()                      # clear a latched error state before trying to move
    return ctl.probe_position() is not None
```

And read the table you are about to write through, instead of trusting the document:

```python
slots = ctl.show_array("CMDS")        # print all entries, compare with the doc, then write
```

When a latched motion error survives reset, relaunch the workcell instead of retrying: on this device
the clean window after a relaunch is 30–90 s, which is the right budget for a short burst of motion
work rather than a long poll that burns it.

## Verification

```console
$ python3 bringup_and_run.py --expect-host ROBOT
ready (copy echo: Copied)          <- runtime layer answered
CMDS[12] = ''                      <- read back, not assumed
run X -> accepted
program state -> DONE (not ABORTED)
position delta -> non-zero
```

Before the fix the same script printed `accepted` for every step and a zero position delta.
