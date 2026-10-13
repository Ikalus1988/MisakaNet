---
domain: "backend"
title: "Fix FastAPI async background task concurrency and event loop isolation"
tags:
  - "fastapi"
  - "asyncio"
  - "background-tasks"
  - "python"
status: "published"
evidence_level: "E1"
summary_plain: "FastAPI 背景任务在协程中执行阻塞 IO 会耗尽主事件循环，应使用 asyncio.to_thread 进行线程隔离调度。"
trigger: "FastAPI async route hangs when BackgroundTasks executes long-running CPU or blocking IO operations"
verify: "pytest tests/test_background_tasks.py -k test_async_worker_nonblocking 退出码为 0"
---

# Fix FastAPI async background task concurrency and event loop isolation

## Problem

When adding long-running background tasks in FastAPI via `BackgroundTasks.add_task(async_fn)`, executing synchronous blocking calls or CPU-bound tasks inside `async_fn` starves the main event loop, causing severe latency spikes on incoming HTTP requests.

## Root Cause

Async functions queued in FastAPI background tasks execute on the main asyncio event loop thread. If the task invokes synchronous blocking I/O (e.g. `requests.get` or filesystem sync calls), the single-threaded event loop cannot process concurrent HTTP requests.

## Solution

Offload blocking background tasks to the worker threadpool using `asyncio.to_thread` or define them as standard synchronous `def` functions, which FastAPI automatically routes to its anyio worker threadpool:

```python
def sync_worker_task(payload: dict):
    heavy_blocking_sync_call(payload)

@app.post("/items/")
async def create_item(background_tasks: BackgroundTasks):
    background_tasks.add_task(sync_worker_task, {"id": 1})
    return {"status": "queued"}
```

## Verification

Execute an integration load test verifying the HTTP endpoint responds in sub-50ms while background worker processes payload:
```bash
python -m pytest tests/test_background_tasks.py -k test_async_worker_nonblocking
```

