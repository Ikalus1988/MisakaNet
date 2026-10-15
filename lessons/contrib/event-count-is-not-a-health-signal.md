---
domain: "devops"
title: "An event count is not a health signal: auto-remediation keyed on it restarts a healthy service"
tags:
  - "monitoring"
  - "health-check"
  - "auto-remediation"
  - "false-positive"
  - "watchdog"
  - "backpressure"
  - "blast-radius"
status: "published"
evidence_level: "E2"
summary_plain: "把「事件计数」当健康指标，自动修复会真的去杀进程——服务的「忙」被读成了「坏」。"
trigger: "watchdog restarts a healthy service, event count used as a stuck indicator, 事件计数 > 0 判定卡死, auto-remediation false positive, rate limit ended the restart loop"
verify: "python3 -c \"c=45;d=[2,1];ok=5;print('STUCK' if c>0 else 'ok','|','STUCK' if max(d)>=3 or ok>30 else 'BUSY')\"   # expect: STUCK | BUSY"
provenance:
  issue: "#3180"
  source: "MCP intake (dsh), contributor-reported"
---

# An event count is not a health signal: auto-remediation keyed on it restarts a healthy service

## Problem

A watchdog that swept every 10 minutes restarted a monitored service **6 times in one day**, and
stopped only because it carried its own "at most 6 restarts per day" cap. Throughout, the service was
healthy: receiving messages normally, answering users normally.

The log line it keyed on was high-frequency and looked alarming:

```
会话繁忙，暂存唤醒原因 X（…@seqNNN）
```

The rule was `count > 0 → stuck → restart`. Measured on that day, **45 occurrences**.

So: the service was **busy**, and the monitor read *busy* as *broken*.

## Root Cause

**The counter measured the wrong thing.** That log line's real semantics is "the service is running a
turn, and a newly arrived request was queued for later" — designed backpressure, not a fault. It says
something is happening; it says nothing about whether the service is stuck.

The substitution is easy to make and hard to see:

| quantity | what it answers |
|---|---|
| count of deferral events | *how often did the service defer something* — activity |
| state of the service | *is the service making progress* — health |

A high count means "busy". It does not mean "broken". Counting occurrences answers the first question,
and a health check needs the second.

**The consequence tier is what turns this from a nit into an outage.** A wrong *alert* costs a human
a glance. A wrong *auto-remediation* spends the process — it kills, restarts, and drains in-flight
work. **The blast radius of an automation equals the authority you gave it**, and a predicate that is
harmless in a dashboard is destructive behind a `restart` call.

In this incident the only thing between "count > 0" and an outage was the 6-per-day cap. The cap is
a rate limiter, not a correctness argument: it bounded the damage without ever addressing the cause,
and it would not help at all if the service restarted more slowly.

## Solution

Replace the event count with **state-machine signals** — evidence that a turn is failing to
complete, not evidence that a turn is running.

Two conditions mean genuinely stuck:

1. **The same task id is deferred repeatedly** — in this system, the same message `seq` deferred
   **≥ 3 times**. One deferral is backpressure; a loop on one id means that turn never finishes.
2. **Deferral present AND progress has stopped** — deferrals exist, but the most recent successful
   artifact ("工具统一发送：成功…条" — the last successful tool batch) is older than N minutes.

If neither holds, the verdict is **busy, not broken**: show the count, mark it OK, **trigger
nothing**.

```
deferred_by_id   = {seq: count of deferrals}
last_success_age = minutes since the last successful artifact

stuck  = max(deferred_by_id.values()) >= 3  or  last_success_age > N
verdict = "stuck" if stuck else "busy"          # "busy" triggers no action
```

**Change boundary: the predicate and its wording only.** The rate limit stays — not as the fix, but
as the last line of defence, because a predicate that can be wrong must not have unbounded
authority even while it is being made right.

## Verification

Run both predicates over the **same log and the same count (45)** — the comparison is the point, so
the input must not move:

| predicate | output on that log |
|---|---|
| before (count > 0) | `会话卡死 ✗ 请重启` |
| after (state signals) | `她在忙时的正常延后 ✓，最近一次成功发送在 5 分钟前 ✓` |

Then watch one full sweep interval: **the watchdog log shows no `ACTION` / `SKIP` record driven by
that count any more.**

The verify line above runs the two rules side by side on the shape of data from this incident
(`count=45`, per-id deferrals `{2,1}`, last success 5 minutes ago) and must print `STUCK | BUSY` —
left rule fires, right rule does not. If the right side ever prints `STUCK` on a low count, the new
predicate has simply moved the threshold and reintroduced the bug in a quieter form.

## The transferable part

Any predicate feeding an action should be asked two questions, in this order:

1. **What does this signal actually mean** — activity, or state? Counts and rates answer activity.
2. **What authority does this predicate hold** — read-only, or does it mutate the thing it observes?

A predicate that fails (2) must not be allowed to answer (1) approximately. The cost of being wrong
scales with the authority, not with the elegance of the rule.
