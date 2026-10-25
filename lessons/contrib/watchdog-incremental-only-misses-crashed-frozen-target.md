---
domain: "devops"
title: "A watchdog that only matches new crash lines stays silent when the target is already dead"
tags:
  - "watchdog"
  - "monitoring"
  - "frozen-log"
  - "fake-alive"
  - "cpu-sampling"
  - "baseline"
  - "recovery"
  - "zombie-process"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
source: "intake-3519"
summary_plain: "看门狗只等「日志里新增崩溃签名」，可目标早就崩了、进程假活、日志不再增长，于是它一直静默、既不告警也不重启。"
trigger: "watchdog silent on already-crashed target, no new crash signature, frozen log bytes, Responding True but CPU delta 0"
verify: "With the target in crashed-residual state (frozen log + terminal code + live process at ~0 CPU), the watchdog prints a stuck verdict and recovers within 180 s instead of waiting."
provenance:
  issue: "#3519"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# A watchdog that only matches new crash lines stays silent when the target is already dead

## Problem

A watchdog was written for a service that crashes repeatedly. Its trigger condition was a delta:

> a **new** crash signature appeared in the log

During the self-test it did nothing. The reason was not a bug in the watchdog — the condition it was
watching for could no longer become true:

- the target **had already crashed**;
- the process was **still sitting there**, reporting `Responding=True` while doing nothing — alive on
  paper, dead in fact;
- the log **would never grow again**.

So the watchdog stayed completely silent: no alert, no restart, and no MTBF samples. It looked like a
healthy, quiet service. The monitoring subsystem that was supposed to produce the MTBF data collected
nothing at all, which meant the availability figure had no data behind it.

The failure being watched for was not "a crash about to happen". It was "a crash that already
happened" — and by construction that produces no new log line.

## Root Cause

**A watchdog keyed on incremental errors assumes you were present when the crash happened.** The
mechanism is sound only in that world: you are watching, the process dies, the log gains a line, the
delta fires.

Real incidents do not cooperate. Crashes happen during unattended hours. By the time anyone deploys,
restarts, or even looks at the watchdog, the target may already be in a **post-crash residual state**:

| what the watchdog expects | what the residual state provides |
|---|---|
| a new crash signature arrives | the crash happened *before* the watchdog started; the signature is already spent |
| log keeps producing lines | the log is frozen at the last line |
| process death is observable | the process is a **fake-alive** remnant — present in the process table, serving nothing |

With `delta == 0` by construction, the predicate can never fire. The watchdog reports "healthy" forever
because it only ever compares against the moment it started looking.

**The three signals that identify the residual state**, and why each is needed:

1. **No progress** — log byte count has zero growth for a continuous period.
2. **Crash residue** — the log already contains a terminal signature (in the reported system, an
   `OS -145` / "power off to reset" style code, i.e. the crash's own terminal line).
3. **Process still there, but dead** — present in the process table with a CPU sample delta of ~0.

Any one of them alone is ambiguous: a quiet service produces (1); a service that once crashed and was
restarted produces (2); an idle-but-healthy service produces (3). **The conjunction means "crashed and
stuck"**: it failed, it left its residue, it is still resident, and it is doing no work.

## Solution

Add **terminal-state detection** alongside incremental error matching. The reported predicate:

```
frozen_for = seconds the log has had zero byte growth

if frozen_for >= threshold            # e.g. 180 s
   and log contains a terminal error code   # e.g. OS -145 / power off to reset
   and the monitored process is still running
   and CPU sample delta is ~0               # fake-alive criterion
then verdict = "crashed and stuck" → perform recovery
```

Keep the incremental-error path as well. The two predicates answer different questions:

| path | question | fires when |
|---|---|---|
| incremental | did a new crash just happen while I was watching? | crash occurs after watchdog start |
| terminal-state | is the target already dead and stuck right now? | crash occurred at any point, including before start |

### 1. Fake-alive: use CPU sampling, never the `Responding` property

`Responding` reflects whether a GUI message queue is being serviced. A hung process can keep answering
it — the window drags, the process "responds", and no work is being done. The reported criterion is a
**CPU sample delta ≈ 0 over 3 seconds** (reported threshold: `≤ 0.1`). That measures *progress*, which is
the thing that is actually absent.

### 2. The baseline must be able to heal itself

The residual state's log size is a **historical cumulative value**. After the recovery restart, the log
is rewritten and the byte count resets toward zero — so a baseline stored across the restart produces a
**negative delta**, and every follow-on comparison is wrong.

Re-anchor the baseline whenever the log size drops significantly between samples:

```python
size = os.stat(log_path).st_size
if size < last_size:          # log was rewritten/truncated by a restart
    last_size = size          # re-anchor; do not compute a delta across the boundary
    return
```

Without this, the watchdog recovers once and then misbehaves silently — the worst kind of fix.

### 3. Do not share a tail with the thing you are restarting

`tail -f`-style monitoring breaks when the monitor and the target restart on different schedules: the
file handle follows the old inode, the restarted target writes to a new one, and the monitor reads a
frozen stream while claiming to be tailing a live one. The reported guidance is to prefer polling by
path (re-`stat`/re-open each cycle) or to make the monitor reconnect. The monitor and the monitored
object must not depend on each other's lifetime.

## Verification

Put the target into the residual state **by hand** — do not wait for a real crash:

1. Let the service crash and leave the process parked (or kill it into the hung/fake-alive state);
2. confirm its log is no longer growing and already contains the terminal signature;
3. start the watchdog.

Expected: within the freeze threshold (`180 s` in the report) the watchdog emits a **stuck** verdict and
performs the recovery. It must not sit silent waiting for an error that has already been written.

Not expecting: it should not linger indefinitely with no output, and it should not need a manual nudge.

After the recovery:

- the baseline re-anchors to the new session's count (zero or the current value), not the pre-crash
  total;
- a **new** crash after the restart is still detected through the incremental path — the terminal-state
  predicate must not have replaced it;
- re-running the same scenario reproduces the stuck verdict, so the behaviour is not a one-off.

The discriminator between "the loop stopped" and "the detector works": in the same setup, the pre-fix
watchdog prints nothing at all for the full threshold window, while the post-fix one prints exactly one
stuck verdict and one recovery.

## Notes

- Evidence level E1: one operator's account of the self-test, with the predicate and thresholds as
  reported; not reproduced in this repository. `OS -145` / the "power off to reset" code are that
  system's terminal signature — substitute your own target's terminal log line.
- **Threshold choice is a trade-off you must state:** too low and a legitimately idle service is
  restarted (see `event-count-is-not-a-health-signal`, where exactly that killed a healthy service 6
  times in a day); too high and the target stays dead for that long. The conjunction above exists to make
  a low threshold safe: idleness alone cannot satisfy it.
- **The self-test deserves its own attention.** This defect was caught only because the self-test set up
  the *already-crashed* state instead of waiting for a live crash. A watchdog tested only against a
  fresh crash will always pass.
- Recovery means the interruption happens — every recovered crash still costs the in-progress work and a
  full restart cycle. Report that cost, not just the recovery success rate
  (`auto-recovery-hides-downtime-effective-availability`).
- `Responding=True` is a liveness signal for a message loop, not evidence of progress. Anywhere it is
  used as "the process is fine", the CPU/progress measurement is missing.
