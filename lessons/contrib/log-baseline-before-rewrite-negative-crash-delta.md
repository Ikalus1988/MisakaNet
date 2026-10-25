---
title: "A baseline captured before the log rewrite turns crash deltas negative and hides the first crash"
domain: "testing"
tags:
  - "log-monitoring"
  - "baseline"
  - "crash-detection"
  - "delta"
  - "verification"
  - "roboguide"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "重启后统计日志里的崩溃增量会出负数，是因为基线在日志被重写之前就读了；等文件被截短再取基线。"
trigger: "delta crash negative after restart baseline logfile rewritten truncated monitoring script"
verify: "The baseline row reads all zeros, event counts are monotone non-decreasing, and a crash-free window reports delta 0, never a negative number."
source: "intake-3469"
provenance:
  issue: "#3469"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# A baseline captured before the log rewrite turns crash deltas negative and hides the first crash

## Problem

Monitoring "did the restart produce a new crash signature in the log" produced a distorted result:
the delta was a large negative number and the first crash was reported as none.

Field notes from the reporter:

- the simulated controller **rewrites** its `logfile.txt` every time a work unit is opened — the old
  file was 27,841 bytes, and once the new session started it was truncated to 7,623 bytes and then
  grew again;
- the monitoring script read the log once, right after "kill the process → start a new session", and
  used that reading as the baseline — but it was still the **old** session's cumulative value
  (`crash=47`);
- once the new session rewrote the file, the counters restarted from zero.

So the summary said:

```
delta: {'crash': -41, ...}
首次崩溃: 无
```

while the raw sample table plainly showed `crash` going 0 → 6 at 315 s. The first-crash test used
`cur > baseline(47)` as well, and the new session never got above 6, so that test could not fire.

## Root Cause

**The baseline was captured before the log was rewritten.** Whenever a restart rebuilds the log
file, pre-restart history cannot serve as the post-restart baseline — the subtraction happens in a
different coordinate system.

The criterion is hard: event counters only increase. A **negative** delta for an event count is
logically impossible, so it almost always means the baseline was anchored wrong, not that things
improved.

## Solution

Anchor the baseline **after** the log has been rewritten by the new session. A runnable test: poll
the file length; when it has clearly dropped (for example below 90 % of the previous length) the
file has been rewritten, and only then take the baseline.

```python
pre_bytes = len(read_log())
for i in range(N):
    raw = read_log()
    if 0 < len(raw) < pre_bytes * 0.9:   # rewritten by the new session
        base = counts(raw)
        break
    sleep(interval)
```

### Step 1 — wait for the truncation, not a fixed sleep

A fixed sleep is a guess about how long the rewrite takes; the length drop is the event itself, so
polling for it is what makes the baseline correct rather than lucky.

### Step 2 — record both the first trigger signature and the first crash signature

The gap between the two is evidence in its own right: here the trigger signature appeared about 30 s
before the crash, and that ordering points back at the trigger mechanism, which is more useful than a
single crash timestamp.

### Step 3 — keep the raw per-sample table

Both rounds, the truth was in the table and the summary fields were the wrong part. Treat the raw
samples as the single source of truth and the summary as a view over them.

## Verification

Re-run the same scene after the fix:

- the baseline row reads all zeros (`crash: 0, os145: 0, ...`), not the old session's cumulative
  values;
- event counts over the window are monotone non-decreasing;
- a crash-free window reports `delta: 0`, never a negative number;
- the first-crash time is either a concrete second or an explicit "none", and it agrees with the raw
  table.

Reported criteria; not re-run in this repository. The real log path and the meaning of the other
counters (`os145` among them) were not given — 报料者未给出，需复现确认.
