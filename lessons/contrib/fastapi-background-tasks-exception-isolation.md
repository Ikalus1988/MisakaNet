---
domain: "backend"
title: "Isolate exceptions in FastAPI background tasks to prevent silent job loss"
tags:
  - "fastapi"
  - "starlette"
  - "background-tasks"
  - "asyncio"
  - "error-handling"
status: "published"
evidence_level: "E1"
summary_plain: "FastAPI 的 BackgroundTasks 抛出异常会直接中断后续任务，必须在任务函数内部捕获并记录日志。"
trigger: "FastAPI BackgroundTasks unhandled exception silent job abort"
verify: "pytest tests/test_background_tasks_isolation.py 退出码为 0"
---

# Isolate exceptions in FastAPI background tasks to prevent silent job loss

## Problem

When multiple jobs are queued in FastAPI's `BackgroundTasks`, an unhandled exception in one job causes all remaining queued background tasks for that request to be skipped without structured alerts.

## Root Cause

Starlette's `BackgroundTasks` executes queued callables sequentially in a loop. When an exception is raised from a task callable, the loop terminates abruptly unless an explicit try/except block wraps the execution logic.

## Solution

Wrap background task bodies with structured error handling and log failures cleanly:

### Step 1: Implement defensive task wrappers
```python
import logging
from typing import Callable, Any

logger = logging.getLogger(__name__)

async def safe_background_task(func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
    try:
        if asyncio.iscoroutinefunction(func):
            await func(*args, **kwargs)
        else:
            func(*args, **kwargs)
    except Exception as exc:
        logger.error(f"Background task {func.__name__} failed: {exc}", exc_info=True)
```

### Step 2: Queue using the defensive wrapper
```python
@app.post("/submit")
async def handle_submit(background_tasks: BackgroundTasks):
    background_tasks.add_task(safe_background_task, process_data, item_id=42)
    return {"status": "accepted"}
```

## Verification

Queue multiple tasks where the first task deliberately raises an exception, and verify subsequent tasks execute to completion.
