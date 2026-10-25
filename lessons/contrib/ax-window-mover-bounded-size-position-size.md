---
title: "Bounding an AX size → position → size sequence: retries, settle, revalidate, and fail loudly"
domain: "development"
tags:
  - "macos"
  - "accessibility"
  - "axuielement"
  - "window-placement"
  - "resize"
  - "bounded-operations"
  - "retry"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "size→position→size 必须是有界序列：先按可见区域夹取请求值，每次写前重验目标，限次重试加 settle，收敛失败要报错而不是缓存成新上限。"
trigger: "AX window mover bounded size position size retry settle revalidate target abort on drag"
verify: "假 AX 驱动下：每个屏幕角与 Center 各放大一次，均在 N 次内收敛到请求尺寸；取消/拖动/拒绝写入各一例，均以明确失败结束而非静默。"
source: "intake-3663"
provenance:
  issue: "#3663"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported symptom; the bounding rules below are derived from AX write semantics, not from a recorded live run in this repository."
---

# Bounding an AX size → position → size sequence: retries, settle, revalidate, and fail loudly

## Problem

A macOS Accessibility window mover applies a requested frame to a window that may be sitting at a
display edge. The correct write order is **size → position → size**: the first size write may be
clamped by the edge, the position write moves the window off the edge, and the second size write is
the one that actually applies the request.

That order is necessary but not sufficient. Three writes are three separate transactions against a
system that is changing underneath them, and the naive implementation has no answer for:

- the window moving to another display between write 1 and write 3
- the user grabbing the title bar mid-sequence
- an AX call that never returns
- a sequence that simply does not converge, retried forever

## Root Cause

An AX write is not atomic with the state it was computed from. `AXUIElementSetAttributeValue`
resolves the requested value against the window's *current* frame, so the result of write 3 depends on
whether write 2 landed, whether the window is still on the same display, and whether anything else is
writing the same attributes. A sequence with no bounds treats all of that as if it were stable.

The second defect is the exit condition. "Read the size back and store it" has no notion of *done*,
so a clamped intermediate value gets recorded as the app's maximum and every later request is bounded
by a number the app never declared.

## Solution

Bound the sequence on four axes. Each bound is cheap; together they turn an unbounded loop into an
operation with a defined end state.

### Step 1 — bound the values before the first write

Clamp the requested rect to the target display's `visibleFrame` **before** writing anything. The first
write is then already legal, and the edge-clamp path becomes the exception rather than the norm.

### Step 2 — bound the attempts and the settle

```
maxAttempts = 3
settleMs    = 50..120, increasing per attempt
```

After each attempt, read the frame back and compare against the request. Converged → done. Not
converged and attempts remain → wait `settleMs`, then retry the **whole** sequence from write 1 (not
from write 3 — the window may have moved back to an edge).

### Step 3 — revalidate the target before every write

Before each of the three writes, and before trusting each readback, re-check:

- the pid and window id are still the ones the sequence started with
- no mouse button is down / no drag is in progress
- the window is still on the display the frame was computed for

Any check failing aborts the sequence with a distinct reason. Do not "fix up" a window the user is
dragging.

### Step 4 — bound the AX call itself

Each AX call gets a deadline. A call past its deadline is a failed attempt, not a hang; the retry
budget absorbs it.

### Step 5 — fail loudly, and only cache settled values

Exhausting `maxAttempts` is a **reported failure** carrying the last observed frame. It is not a new
maximum. Only a value that comes back identically on two consecutive settled readbacks may be
recorded as an app-imposed min/max.

### Step 6 — make the sequence resumable

A cancellation between write 2 and write 3 leaves the window at the new position with the old size.
That is a legal intermediate state, so a cancelled sequence can be re-run from write 1 without
special-casing; do not roll back to the original frame.

## Verification

A deterministic **fake AX driver** is the testable form: it clamps a requested size against the
current frame, can move the window between displays, can reject a position write, and can delay a
call past its deadline.

Cases that must pass:

- every display corner plus Center, each growing the window — all converge within `maxAttempts`
- cross-display placement
- app-declared minimum size
- delayed read and delayed write
- cancellation arriving between writes
- a rejected position write
- a slow AX call past its deadline
- a window that never converges — ends in a reported failure, and the cached max is unchanged

## Notes

- **Not verified live.** The bounding rules are derived from AX write semantics; the reporter's own
  live acceptance was inconclusive. The fake driver is the proof; a hardware pass is still owed.
- The write order itself, and the readback-cached-as-maximum defect, are covered in
  `lessons/contrib/ax-window-resize-clamps-at-edge-reorder-writes.md`. This lesson only adds the
  bounds around that sequence.
- Generalisation: any multi-write geometry operation against a live system needs a value clamp, an
  attempt budget, a settle, a revalidation, and a failure that is distinguishable from success.
