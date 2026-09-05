---
title: Python asyncio CancelledError Silently Swallows Resources in Long-Running Services
domain: python
tags:
- python
- asyncio
- cancellederror
- resource-leak
- task-cleanup
status: published
created: '2026-08-27'
source: intake-issue-1298
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

# Python asyncio CancelledError Silently Swallows Resources

## Problem

Python asyncio task exception handler silently swallows CancelledError when task is cancelled during await, leading to resource leaks in long-running services. Error message:

```
Task was destroyed but it is pending! task: <Task pending name=Task-42 coro=<fetch_data() running at /app/service.py:123>>
```

## Root Cause

When an asyncio task is cancelled (e.g., via `task.cancel()`), the CancelledError is raised inside the coroutine. If the coroutine doesn't properly handle cleanup in a `finally` block or the exception handler catches and ignores CancelledError, resources held by the task (file handles, connections, locks) are never released. Python's garbage collector eventually destroys the task, but by then the warning "Task was destroyed but it is pending" has already been emitted, and resources may have leaked.

## Solution

Use `task.add_done_callback()` to check for CancelledError and clean up resources explicitly before the task is garbage collected:

```python
import asyncio

async def fetch_data():
    conn = await create_connection()
    try:
        return await conn.read()
    finally:
        await conn.close()  # Cleanup on any exit

async def safe_task_wrapper(coro):
    task = asyncio.create_task(coro)
    
    def cleanup_callback(t):
        if t.cancelled():
            print(f"Task {t.get_name()} was cancelled, cleaning up")
            # Any additional cleanup here
    
    task.add_done_callback(cleanup_callback)
    return task

# Usage
task = await safe_task_wrapper(fetch_data())
```

Alternative: Use `asyncio.shield()` to prevent cancellation of critical sections, but this doesn't solve the cleanup problem — it only defers it.

## Verification

```python
# test_cancellederror_cleanup.py
import asyncio
import pytest

@pytest.mark.asyncio
async def test_cleanup_on_cancel():
    cleanup_ran = False
    
    async def resource_task():
        nonlocal cleanup_ran
        try:
            await asyncio.sleep(100)  # Long-running operation
        finally:
            cleanup_ran = True
    
    task = asyncio.create_task(resource_task())
    await asyncio.sleep(0.1)  # Let it start
    task.cancel()
    
    try:
        await task
    except asyncio.CancelledError:
        pass
    
    assert cleanup_ran, "Cleanup did not run on cancellation"
```

```bash
pytest test_cancellederror_cleanup.py -v
```

**Expected Output:**
```
test_cancellederror_cleanup.py::test_cleanup_on_cancel PASSED
```