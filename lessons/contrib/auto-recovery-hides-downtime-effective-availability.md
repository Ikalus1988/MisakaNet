---
domain: "devops"
title: "Auto-recovery hides the outage: report effective availability, not the recovery success rate"
tags:
  - "availability"
  - "mtbf"
  - "watchdog"
  - "monitoring"
  - "incident-severity"
  - "metrics"
  - "recovery"
  - "downtime"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
source: "intake-3521"
summary_plain: "「有看门狗会自动恢复」把每天 41 次、合计 55 分钟的中断说成了已治理；恢复能力不等于可用性。"
trigger: "watchdog auto-recovery lowers ticket priority, short MTBF, reporting recovery success rate instead of effective availability"
verify: "python3 -c \"m=11.7;r=80/60;print(round(m/(m+r),3),round(480/m),round(480/m*r))\"  # expect: 0.898 41 55 — availability, daily interruptions, daily downtime minutes"
provenance:
  issue: "#3521"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# Auto-recovery hides the outage: report effective availability, not the recovery success rate

## Problem

A service failed repeatedly, and a watchdog had been set up to bring it back automatically. When the
incident was filed, it was described like this:

> 有看门狗，能自动恢复。

The ticket's priority was then set very low. On paper the reasoning is fine — nobody has to be paged,
the service comes back by itself.

**Auto-recovery made the problem look smaller than it was.** Read the log alone and it reads like an
operations success: "crashed N times, all N recovered automatically". Nothing in that line says the
service was *unavailable*.

What each of those recoveries actually meant:

- the task in progress was interrupted and its state discarded;
- a full restart cycle had to complete before the service could serve again;
- throughout that cycle, the workstation / the service was **completely unavailable**.

Auto-recovery replaces *manual intervention* with *automatic downtime*. It is not availability.

## Root Cause

**Recovery capability was reported as if it were availability.** They are different dimensions, and
only one of them belongs in a severity decision:

| dimension | question it answers | unit |
|---|---|---|
| recovery capability | after a failure, does it return to a serving state on its own? | yes / no |
| availability | what fraction of wall-clock time is it actually serving? | percent |

A system with automatic recovery **and a short MTBF** still has low availability: it spends a large
share of every hour failing and restarting. Recovery answers "do we need a human?"; availability answers
"can anyone use this?".

Reporting only the recovery success rate converts an availability problem into an automation
achievement. The decision-maker reads "risk eliminated" and lowers the priority — which is exactly the
wrong conclusion, because the *rate* of disruption is unchanged and, in this case, extreme.

## Solution

Quantify the residual impact with **effective availability**:

```
effective availability = MTBF / (MTBF + recovery cost)
```

- `MTBF` — mean time between failures (the interval between crash events).
- `recovery cost` — the whole time to get back to serving, not just process spawn: process restart +
  application bootstrap + state rebuild. Measure it end to end; the spawn time alone flatters the
  number by an order of magnitude.

Then add two conversions so a non-specialist can feel the severity:

```
failures per workday = work hours / MTBF
daily cumulative downtime = failures per workday × recovery cost
```

**The measured example from the report:** MTBF ≈ 11 minutes, recovery cost ≈ 80 seconds.

```
effective availability = 11.7 / (11.7 + 1.33) ≈ 0.898        → ~90%
failures per 8 h day   = 480 / 11.7          ≈ 41
daily downtime         = 41 × 1.33 min       ≈ 55 min
```

**"90%" sounds acceptable. "41 interruptions and 55 minutes unavailable per working day" is what the
decision actually needs.** Give both — the percentage for comparison, the counts for severity — and
never the percentage on its own.

### Two rules for the write-up

1. **Report the recovery success rate and the effective availability together**, and label the
   distinction explicitly: "recovery ≠ availability". A recovery rate of 100% next to 90% availability
   is a coherent and alarming pair; the 100% alone reads as health.
2. **State the business cost of one interruption.** What is lost each time — the in-progress task, the
   live session, unflushed state? A concrete list ("each of the 41 daily interruptions discards the
   work in progress and nobody can use the station for ~80 s") moves priority more reliably than any
   percentage, because it names what the user loses.

### Rewriting the ticket line

Before, an automation status report:

> 有看门狗，能自动恢复。

After, an availability report:

> 该服务每工作日约 41 次崩溃，每次自动恢复约 80 秒（含重启与状态重建），有效可用率约 90%，
> 日累计不可用约 55 分钟。恢复成功率 100%，但恢复不等于可用。每次中断会丢弃当前进行中的任务。

Same facts. One of them gets deprioritised.

## Verification

A write-up passes only if it contains **both** an effective availability figure and a per-day
interruption count (with recovery cost defined). If the report has only "crash count" and "recovery
success rate", the write-up is insufficient — that is the failure criterion, and it is checkable
without re-running anything:

1. Report contains `MTBF`, `recovery cost`, `effective availability`, `failures per workday`.
2. `MTBF / (MTBF + recovery cost)` reproduces the availability number from the stated inputs.
3. The recovery cost covers the whole outage window; if it counts only process start, the availability
   number is inflated and the report fails.
4. Answer the question the reader will actually ask — "can this be used in production?" — from the
   availability and interruption figures, not from the recovery success rate.

The frontmatter `verify` command (MTBF 11.7 min, 80 s recovery) must print `0.898 41 55`; a different
answer means the arithmetic in the report does not follow the formula.

## Notes

- Evidence level E1: one operator's incident, with MTBF, recovery cost and the three quoted figures;
  not reproduced in this repository. The 11.7-minute MTBF is the rounded figure the report's own
  numbers imply ("约 11 分钟", 41 failures in 8 h), not a separately measured value.
- **Why recovery cost is so often underestimated:** restarts are measured from the watchdog's
  perspective (spawn → exit), while unavailability runs from the user's (last good response → first
  good response). Application bootstrap and state rebuild are inside the user's window and outside the
  watchdog's.
- **A watchdog that restarts a healthy service is the mirror failure** — there the fix is the predicate,
  not the reporting (`event-count-is-not-a-health-signal`). Both land on the same lesson: the recovery
  mechanism must not be used as the health metric.
- **A watchdog that never fires because the target was already dead** is the third member of this
  family: MTBF sampling then collects nothing at all, so the availability figure has no data behind it
  (`watchdog-incremental-only-misses-crashed-frozen-target`).
- If the failures genuinely cannot be fixed, the honest framing is a decision input, not a success
  story: "this is a 90%-available service" is a deployment decision someone must make consciously.
