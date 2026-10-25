---
domain: "devops"
title: "A precursor that fires repeatedly is not a countdown: fixed-delay warning windows miss the failure"
tags:
  - "monitoring"
  - "alerting"
  - "precursor"
  - "warning-window"
  - "incident-analysis"
  - "sampling"
  - "mttd"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
source: "intake-3520"
summary_plain: "按「前兆比故障早 30 秒」设预警窗，但前兆在一个故障周期里反复触发，提前量其实从 15 秒到几分钟不等。"
trigger: "precursor signal fires multiple times before crash, fixed 30 second delay warning window, lead time varies from 15s to minutes"
verify: "Over 3+ complete failure cycles, per-cycle precursor count is >1 and the first-to-failure spread is much wider than the last-to-failure spread; a fixed second-based window cannot cover that."
provenance:
  issue: "#3520"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# A precursor that fires repeatedly is not a countdown: fixed-delay warning windows miss the failure

## Problem

A crashing service emitted a precursor signal before failing. From one or two observations, the gap was
estimated as a fixed delay — "the trigger signature appears 30 seconds before the crash" — and that
number was designed into the alerting: arm a warning window N seconds before the expected failure.

The number then propagated. It appeared as settled fact in several write-ups ("触发签名早于崩溃 30 秒"),
each one building on the estimate rather than on a measurement.

Continuing to sample broke it. The precursor is **not a one-shot event**:

- the same precursor fires **repeatedly inside a single failure cycle** — the count goes 1, 2, 3…;
- the failure can arrive after **any** of those occurrences;
- the observed precursor→failure gap ranged from **15 seconds to several minutes**.

A fixed window therefore fails in both directions:

- **too short (e.g. 30 s):** the first precursor arrives, the window opens and closes, the alert is
  dismissed — and the failure comes minutes later. Net warning: none, but the system *reported* having
  warned.
- **too long:** every occurrence of a repeated precursor holds the alert open for a long time. The
  signal is nearly always on, users learn to ignore it, and it is muted exactly when it matters.

## Root Cause

**"The precursor appeared" was read as "the countdown started".** It is not a countdown. It is closer
to *the trigger conditions are accumulating*: each occurrence means one more unit of accumulation has
happened, not that a timer began at that instant.

Inferring a fixed delay from a single precursor→failure gap treats the **last** accumulation as the
**only** one:

```
observed:  [precursor] ............ 30 s ............ [failure]
model:     fixed 30 s delay
reality:   [p] ... [p] ........ [p] ...... [p] ...... [failure]
           ^ first                   ^ last  \_ the 30 s that got measured
```

The 30 seconds was the tail of an accumulation sequence. With one or two samples there is nothing to
distinguish the tail from the whole.

**The compounding error is social, not statistical:** once "30 seconds" is written into a report as
fact, later observations get reconciled against it rather than replacing it, so a sampling artifact
survives into the design. The next reader has no way to tell an estimate from a measurement.

## Solution

Design the early warning on **accumulation count and rate**, not on a fixed delay window.

### 1. Record precursors as count events, not as moments

Keep every occurrence's timestamp. When the failure happens, compute three quantities per cycle:

```
precursor_count        = number of occurrences in the cycle
first_to_failure       = t(failure) - t(first precursor)   ← lead time available
last_to_failure        = t(failure) - t(last precursor)    ← response time available
```

Two different questions, two different numbers. Conflating them is how the fixed delay was invented:
the second quantity is short and stable; the first is long and variable.

### 2. Alert state is "unresolved", not "timed"

After a precursor appears, hold the alert until one of two things happens:

- the failure occurs (the alert was right), or
- an explicit **healthy** signal arrives — e.g. the log keeps growing with no new precursor for a
  defined period, or the service reports a successful operation.

Do **not** auto-disarm on a fixed number of seconds. A timer encodes an assumption about *when* the
failure comes; "unresolved" only encodes that nothing has resolved it yet, which is true whether the
failure lands in 15 seconds or four minutes.

### 3. Report both numbers with their labels

- "末次前兆→故障" — usable as **response time** for emergency handling.
- "首次前兆→故障" — usable as **early-warning lead time** for design.

Any sentence of the form "the precursor is N seconds before the failure" is incomplete. It must say
*which* precursor: "**the last** precursor was 30 seconds before the failure" and "**the first** precursor
was up to several minutes before it". Use the second figure when sizing a warning window, and the
first when sizing an on-call response.

### Classifying what you have

| observation | what it means | design consequence |
|---|---|---|
| precursor appears once, failure exactly N seconds later, repeatably | true fixed delay | a fixed window is legitimate |
| precursor appears multiple times, failure after any one | cumulative | unresolved alert + cumulative count |
| precursor appears, failure does not follow this time | precursor is not a sufficient condition | the alert must be releasable, or it becomes a permanent false alarm |

The first row is the one people assume. The report's data lands in the second, which is why the fixed
window under-warned.

## Verification

Collect **several complete failure cycles** (not one) and tabulate per cycle:

```python
# t_precursors: list of timestamps, one cycle; t_failure: failure timestamp
count            = len(t_precursors)
first_to_failure = (t_failure - t_precursors[0]).total_seconds()
last_to_failure  = (t_failure - t_precursors[-1]).total_seconds()
```

Then apply the decision rule:

- **`count > 1` in most cycles** → cumulative, not fixed delay;
- **the `first_to_failure` distribution is clearly wider than the `last_to_failure` distribution** →
  the fixed-window design is wrong, switch to unresolved-alert + cumulative count;
- **`last_to_failure` is short and tight while `first_to_failure` is long and wide** → this is the
  exact profile that produces a believable "N seconds" estimate, and the exact profile a fixed window
  cannot cover. It should be treated as evidence *against* the fixed window, not for it.

Also verify the write-up: each claim of the form "N seconds before the failure" carries the qualifier
identifying which precursor it refers to. A report without that qualifier fails verification even if
the number itself is correct.

## Notes

- Evidence level E1: one operator's account, with the precursor counts and the 15 s … several-minutes
  spread as reported; not reproduced in this repository. The specific "30 seconds" was the estimate in
  the reports, not a measured constant.
- **The sample-size trap is the transferable part.** A single precursor→failure pair is
  indistinguishable from a fixed delay. The estimator cannot know it picked the last item of a sequence
  until a second sequence is observed. When a "fixed N seconds" claim is about to enter a design, the
  check is cheap: observe a *second* full cycle before building on it.
- A precursor that sometimes does not lead to a failure means the signal is **necessary but not
  sufficient**. Any design that disarms only on failure therefore needs a health-based release, or it
  fires forever after the first non-followed precursor.
- The false-alarm failure mode is asymmetric in cost: an over-long window does not just annoy, it
  trains people to ignore the signal, so its cost is paid at the one time it was right.
- Related in this corpus: a watchdog keyed on the *increment* of an error signature stops firing once
  the target has already crashed (`watchdog-incremental-only-misses-crashed-frozen-target`) — the same
  family of "the alert condition assumed the failure starts when I am watching".
