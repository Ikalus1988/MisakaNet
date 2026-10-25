---
title: "An AX window keeps its width at a display edge: request size, then position, then size again"
domain: "development"
tags:
  - "macos"
  - "appkit"
  - "accessibility"
  - "axuielement"
  - "window-placement"
  - "resize"
  - "readback"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "窗口贴屏幕边缘时，先调尺寸再移动会被边缘夹住；顺序应是先尺寸、再位置、再尺寸一次。"
trigger: "AXUIElement setFrame window height grows width fixed at display edge clamped"
verify: "贴每个屏幕角与 Center 各触发一次放大，最终 AX 尺寸等于请求尺寸且宽度未变"
source: "intake-3665"
provenance:
  issue: "#3665"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# An AX window keeps its width at a display edge: request size, then position, then size again

## Problem

An AppKit window-placement companion could grow a window's **height while its width stayed fixed**
when the window sat near a display edge. Clicks were received — the app was not frozen — but each
click produced a partially applied geometry change instead of the requested one.

The user recording shows the symptom directly: width fixed, height growing.

The second, quieter failure: the tool **read the window's size back too early and treated a transient
value as the application's maximum**, so a value produced by edge clamping was cached as a genuine
limit the app had imposed.

## Root Cause

`AXUIElementSetAttributeValue(kAXSizeAttribute)` on a window whose right or bottom edge is already at
the edge of the display's visible frame does not fail — it **clamps**. The requested rectangle is
resolved against the current frame, so growing away from a clamped edge yields a size the display
will accept, which is smaller than what was asked for. Any code that writes size and then position is
therefore writing the clamped size and then *moving the clamped size into place*, which preserves the
defect: the window is now at its new position, still the old-ish width.

Reordering the frame is the fix, because the second size write happens after the window has left the
edge.

The cached maximum is a separate defect with the same theme — reading a value before the system has
settled. A readback taken during clamping/settling is a sample of the transition, not a statement of
the app's constraint. Storing it as "the app's maximum" makes the wrong limit permanent, so later
requests are bounded by a value the app never declared.

## Solution

### Step 1 — Write the frame in the order size → position → size

```
1. set size        (may be clamped while the window is still at the edge)
2. set position    (moves the window off the clamped edge)
3. set size again  (now resolves against the new position, so it is not clamped)
```

The third write is not redundant: it is the write that applies the size the caller actually asked
for.

### Step 2 — Guard every AX write against state changes

An AX write is not atomic with the state it was computed from. Before each write (and before
trusting each readback), re-check:

- the target window is still the intended one (pid/window id unchanged)
- the app still has focus in the expected sense
- no mouse button / drag is held
- the window has not moved to another display since the frame was computed

### Step 3 — Bound settling and retries; read back real constraints

Retry the write sequence a bounded number of times with a settle interval, and treat "still not the
requested size after N attempts" as a failure to report — not as a new maximum to cache. Only values
that come back consistently, after settling, may be recorded as app-imposed minimum/maximum.

## Verification

A deterministic **fake AX driver** is the testable form of this fix: it reproduces edge clamping
(it clamps a requested size against the current frame) and lets the suite assert convergence.

Cases that must pass, per the reporter's suite:

- every display corner plus Center
- cross-display placement
- app minimum sizes
- delayed read and delayed write
- cancellation arriving between writes
- a rejected position write
- a slow AX call past its deadline

The reporter ran 14 focused operation cases within a 152-test suite, plus the user recording showing
width fixed while height grows.

**Not verified live.** The signed update was installed, but live automated acceptance remained
inconclusive because the foreground application changed during the run. This evidence does not claim
live success — the deterministic fake driver is the proof; a hardware/manual pass is still owed.

## Notes

- The generalisation: a clamp is a silent partial success. Any settable rectangle written near a
  boundary needs a write-read-rewrite cycle, and its readback needs to be compared against the
  request, not stored as a discovered limit on first observation.
- Related: display-mode preview state has the same "two states look like one" shape —
  `lessons/contrib/display-preview-restore-session-scope-after-failed-readback.md`.
