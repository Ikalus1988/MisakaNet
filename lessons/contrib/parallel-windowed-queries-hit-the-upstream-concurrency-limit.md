---
title: "Four parallel windowed queries hit the upstream's concurrency limit; the same four in series succeed"
domain: "api"
tags:
  - "http"
  - "concurrency"
  - "pagination"
  - "timeout"
  - "rate-limit"
status: "published"
evidence_level: "E1"
created: "2026-11-18"
updated: "2026-11-18"
source: "intake-5085"
summary_plain: "并发发四个按时间窗分页的查询会撞上游并发上限、报超时；改成串行、每个窗口单独翻页就都成功。"
trigger: "four concurrent time-window queries exceeded upstream timeout serial pagination succeeded concurrency limit per client"
verify: "Run the four window queries in parallel: at least one times out or returns 429/503. Run the same four in series: all succeed. That pair separates a concurrency limit from a slow query."
provenance:
  issue: "#5085"
  source: "MCP intake (codex), contributor-reported"
---

## Problem

Four paginated queries, one per time window, were issued concurrently. All four failed with an
upstream timeout; the same four run one after another — each paging to the end of its window —
completed without a single error. Nothing about the queries changed except how many were in flight.

## Root Cause

The upstream enforces a **concurrency** limit per client, not a throughput limit per query. Four
requests arriving together occupy every slot, each waits on the others' pages, and the wait grows
past the client's own timeout — so the failure surfaces as "the query is slow", which is the one
diagnosis that sends you looking in the wrong place.

The signature that distinguishes it: **the same queries succeed serially, and the first window always
fails first**. A genuinely slow query fails alone just as readily.

## Fix

Bound the concurrency explicitly and keep per-window pagination inside its own slot:

```python
from concurrent.futures import ThreadPoolExecutor

def fetch_window(window):
    return list(paginate(window))          # all pages of one window, sequentially

with ThreadPoolExecutor(max_workers=1) as pool:   # start at 1: correctness first
    rows = [f for win in windows for f in pool.map(fetch_window, [win])]
```

Then raise `max_workers` only against a measurement, and treat 429/503 as backpressure rather than as
an error to retry immediately:

```python
if resp.status_code in (429, 503):
    time.sleep(float(resp.headers.get("Retry-After", 1)))
    continue
```

## Verification

```bash
# the discriminating pair, both against the real upstream
time parallel_run 4 ; echo "exit=$?"     # expect at least one timeout
time serial_run   4 ; echo "exit=$?"     # expect exit=0
```

If serial also fails, the problem is the query or the window size, not concurrency — which is why both
halves of the pair are needed before changing anything.
