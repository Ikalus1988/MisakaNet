---
title: "A cache-expiry test that sets load_time = 0.0 only works when the monotonic clock is already past the TTL"
domain: "testing"
tags:
  - "time-monotonic"
  - "cache-invalidation"
  - "flaky-test"
  - "ci"
  - "clock"
  - "ttl"
  - "python"
status: "published"
evidence_level: "E1"
created: "2026-10-25"
updated: "2026-10-25"
summary_plain: "用 load_time = 0.0 假装缓存很久没更新，只在 monotonic 时钟已经超过 TTL 时成立，刚启动的 CI 机器上就不成立。"
trigger: "cache invalidation test fails on fresh CI runner passes locally load_time 0.0 time.monotonic"
verify: "在 time.monotonic() 还小于 TTL 的新容器里跑该测试应通过；把 load_time 改回 0.0 后在同一容器里必须失败。"
source: "intake-2035"
provenance:
  issue: "#2035"
  source: "MCP intake (reporter)"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

# A cache-expiry test that sets load_time = 0.0 only works when the monotonic clock is already past the TTL

## Problem

Cache-invalidation tests pass on developer machines and fail on fresh CI runners. The tests forced expiration by overwriting the cache's load timestamp with zero:

```python
cache.load_time = 0.0     # "so it is definitely expired"
```

and the cache decided expiry with a TTL check on that same clock. The reporter's description pinned the condition down to `now - 0.0 < 60`; the smallest shape that produces it is:

```python
now = time.monotonic()
expired = (now - self.load_time) > self.interval     # interval is 60 s
```

(That snippet is reconstructed from the reporter's description, not quoted from their code — the cache's own `load_time` assignment and interval constant were not given, see Notes.)

On a laptop that has been up for days, `now` is huge, so `now - 0.0 > 60` is true and the test takes the "expired" path. On a freshly booted runner, `now` is a few seconds — and the same test silently takes the "still fresh" path.

## Root Cause

`time.monotonic()` returns seconds since an arbitrary point, in practice the system boot. It has no epoch and no relation to wall-clock time. `load_time = 0.0` therefore does not mean "an hour ago"; it means "at monotonic zero", and whether that is more than one interval in the past depends on **how long the machine has been up**.

The reporter's condition makes this concrete: the re-check path is guarded by `now - load_time < interval`, which with `load_time = 0.0` becomes `now < 60`. On a runner whose monotonic clock reads 5–30 s the guard is true, the cached entry counts as fresh, the mtime re-check is never entered, and the assertion about the re-check fails — for a reason that has nothing to do with the cache code. `load_time = 0.0` only forces expiry when `now >= interval`.

A second, related coupling: some tests used `os.utime(path, (time.time() + 10, time.time() + 10))` to make the file look newer. That writes a **wall-clock** timestamp into the future to influence a **monotonic-clock** decision. The two clocks can drift or jump (NTP step, suspend/resume), so the test can pass or fail for reasons unrelated to the code under test.

## Solution

Three changes, all on the test side — the cache implementation does not need to change:

1. **Make the timestamp old relative to the clock the code reads**, instead of using a constant:

   ```python
   cache.load_time = time.monotonic() - CACHE_INTERVAL - 1
   ```

   This is "expired" on an uptime of 5 s and on an uptime of 5 days, because it subtracts from the same clock the guard reads.

2. **For mtime-sensitive tests, let real time pass** rather than faking a future timestamp:

   ```python
   time.sleep(0.1)      # let filesystem mtime resolution advance
   path.write_text(new_content)
   ```

3. **Drop the `os.utime` calls.** Writing the file already updates its mtime; the future-dated `utime` existed to beat mtime granularity, which the short sleep handles without touching either clock.

The rule worth keeping: never use `0` as "long ago" for a clock that has no epoch. Any constant that is supposed to mean "in the past" must be derived by subtracting from the clock the production code actually calls.

## Verification

- Reporter's result: CI green on Python 3.9 / 3.10 / 3.11 / 3.12 across all runners; the suite had previously failed on 3.10 and 3.12.
- Reproduce the mechanism in a fresh container (`python3 -c "import time; print(time.monotonic())"` reads less than the cache interval): the fixed suite must pass there, and with `cache.load_time = 0.0` restored it must fail there. If the old form still passes in a fresh container, the test never depended on expiry and the fix is not demonstrated — find the assertion that is actually measuring it.

The discriminating detail is the runner's uptime, not the Python version: a failure that only reproduces on some runners is a failure whose input is environment state, and the monotonic clock is exactly such an input.

## Notes

- The reporter gave the interval as `60` s inside the failing condition (`now - 0.0 < 60`) and named `time.monotonic()` as the cache's clock, but did not give the cache module, the CI provider, or the runner image — 报料者未给出，需复现确认.
- The wall-clock/monotonic coupling in `os.utime` is the same class of bug as the `0.0` constant: a test that injects a value from a different clock than the one the code reads is measuring the clocks' relationship, not the code.
- Domain choice: `testing`. The lesson is about making a test deterministic rather than about a clock API, and the searchable fragment ("fails on fresh CI runner, passes locally") is a testing symptom.
