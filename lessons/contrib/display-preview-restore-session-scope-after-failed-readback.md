---
title: "A display preview that fails to commit must be restored at session scope, not app-only scope"
domain: "development"
tags:
  - "macos"
  - "display-mode"
  - "cgdisplay"
  - "session-scope"
  - "state-machine"
  - "rollback"
  - "preview"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "预览分辨率看似回滚成功，退出应用却又变回那个被拒的分辨率——因为回滚只做了 app 级，没做 session 级。"
trigger: "display mode preview forSession forAppOnly restore rejected resolution on exit"
verify: "注入驱动下 Keep 校验失败后，当前模式与 session 模式都回到原值；退出应用不再出现被拒分辨率"
source: "intake-3656"
provenance:
  issue: "#3656"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# A display preview that fails to commit must be restored at session scope, not app-only scope

## Problem

A macOS display-preview state machine **appeared to revert successfully** and then restored the
rejected resolution on application exit.

The sequence: the user previews a candidate display mode, presses Keep, the tool commits the
candidate with `forSession`, the verification readback fails, and recovery restores the original —
but only with `forAppOnly`. Visibly the screen is back to the original mode, so the rollback looks
correct. When the app exits, the rejected mode comes back.

The reporter found this during source review and reproduced it with an injected driver — **not** by
changing a physical display.

## Root Cause

`forAppOnly` and `forSession` are two different writes, and the tool was tracking one state ("the
visible mode") for both.

- `forAppOnly` sets the mode for the lifetime of the application's connection. It changes what is on
  screen now and is discarded when the process goes away.
- `forSession` sets the session baseline — the mode the login session returns to.

A successful Keep commit is `forSession`. The session baseline is now the rejected candidate. If the
post-commit verification readback then fails, an `forAppOnly` restore fixes the **visible** mode and
leaves the **session baseline** at the rejected value. Both states look identical through the
"what mode is active" query, so the rollback is reported as complete while half of it never happened.
On exit, the session baseline wins.

The same conflation causes the smaller bugs around it:

- Recovery state was dropped after a *failed* restoration, so there was no longer a pending
  obligation to retry — the failure was recorded as "done".
- A preview that completed its temporary-scope write and then failed atomically was treated as
  ownership of a newer external setting, so the tool believed it had superseded a mode change it had
  not actually made.

## Solution

### Step 1 — Track session promotion as its own flag

Record **"has a session-scope commit succeeded?"** separately from "which mode is current". Everything
downstream branches on the flag, not on the visible mode.

```
session_promoted = false   # set true only after a forSession commit succeeds
```

### Step 2 — Choose the restore scope from the flag

- Ordinary preview rollback (nothing was promoted): restore with **temporary / `forAppOnly`** scope.
  This is still the right scope — do not escalate a preview that never committed.
- Successful session commit followed by failed verification: restore the saved original **at session
  scope too**, in addition to restoring the visible mode. Both, in that order.

### Step 3 — Keep pending recovery pending

A restoration that itself fails must leave the pending-recovery obligation in place, so a later tick
or the exit path retries it. Clearing the flag on failure converts "not yet restored" into "nothing
to do".

### Step 4 — Do not claim ownership of a setting you never set

A preview that failed atomically completed no write. Treat that as **no ownership** of a newer
external setting; do not let it suppress someone else's change.

## Verification

A deterministic driver fixture that keeps **current mode and session mode as two separate values** is
the whole point of the test — a fixture with one mode cannot express this bug.

Pass criteria from the reporter's suite:

- Both scopes return to the original after a Keep whose readback fails (the bug case).
- A Keep that fails *before* committing retains temporary-only rollback scope (the non-bug case).
- A failed restoration keeps pending recovery set.

**Not verified live.** Actual AppKit modal timers, abnormal process exit, and real hardware behavior
require separate live acceptance and were not verified.

## Notes

- The generalisation: when a platform has "now" and "persisted" as distinct scopes, a rollback that
  only writes "now" is a partial rollback that reports success. Any preview/apply/commit UI needs the
  commit flag in its state, not just the current value.
- Companion lesson on the same app: window geometry is also written against a stale frame —
  `lessons/contrib/ax-window-resize-clamps-at-edge-reorder-writes.md`.
