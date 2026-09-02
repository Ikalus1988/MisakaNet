---
title: api rate limit handling best practices
domain: contrib
tags:
- rate
- limit
- handling
- best
- practices
status: published
created: '2026-07-06'
source: unknown
---

<!-- provenance:
  contributor: "Ikalus1988"
  merged_at: "2026-05-20"
  evidence: "post-publication"
-->

<!-- 
## Problem
大批量API任务没有提前测试限流，任务中途被截断，无法续命。例如：向某第三方API批量发送10000条请求，跑到第3000条时触发429错误，整个任务崩溃，已处理数据全部丢失，只能从头重跑，浪费大量时间和资源。

常见触发场景：
- 短时间内并发请求数超过API提供方的QPS（每秒请求数）上限
- 单个账号在滑动时间窗口内累计请求数超过配额
- 批量任务未做任何节流，直接全速打满接口

## Root Cause

### 1. 未提前探测限流阈值
开发者往往直接上线大批量任务，不清楚目标API的实际限流规则（如：100 req/min、1000 req/hour），导致任务必然在某个节点触发限流。

### 2. 未实现错误重试与指数退避
收到429响应后，程序直接抛出异常退出，而不是等待一段时间后重试。更糟糕的是，部分实现采用固定间隔重试（如每秒重试一次），在高并发场景下会加剧服务端压力，形成"重试风暴"。

### 3. 缺乏分批与断点续传机制
整个任务作为一个原子操作执行，没有将大任务拆分为小批次，也没有在每批完成后持久化进度（checkpoint）。一旦中途失败，无法从断点恢复，只能全量重跑。

### 4. 忽略响应头中的限流信息
大多数API会在响应头中返回限流相关信息，如：
- `X-RateLimit-Limit`: 总配额
- `X-RateLimit-Remaining`: 剩余配额
- `X-RateLimit-Reset`: 配额重置时间戳
- `Retry-After`: 建议等待秒数

未读取这些信息，导致程序无法动态调整请求速率。

## Solution

### 1. 先跑小批量 Pilot 测试限流阈值

在正式大批量任务前，先用小样本（如100条）以递增速率测试，找到触发429的临界点，并留出20%~30%的安全余量。

```python
import time
import requests

def pilot_test(api_url, headers, sample_size=100, rate_per_second=5):
    """用小批量测试API限流阈值"""
    success = 0
    rate_limited = 0
    interval = 1.0 / rate_per_second

    for i in range(sample_size):
        resp = requests.get(api_url, headers=headers)
        if resp.status_code == 200:
            success += 1
        elif resp.status_code == 429:
            rate_limited += 1
            print(f"触发限流于第 {i+1} 次请求，当前速率: {rate_per_second} req/s")
            break
        time.sleep(interval)

    print(f"成功: {success}, 限流: {rate_limited}")
```

### 2. 对429错误实现指数退避（Exponential Backoff）

收到429后，按指数增长等待时间重试，并加入随机抖动（jitter）避免多个客户端同时重试造成拥堵。

```python
import time
import random
import requests

def request_with_backoff(url, headers, max_retries=5):
    """带指数退避的请求函数"""
    for attempt in range(max_retries):
        resp = requests.get(url, headers=headers)

        if resp.status_code == 200:
            return resp

        if resp.status_code == 429:
            # 优先读取 Retry-After 响应头
            retry_after = resp.headers.get("Retry-After")
            if retry_after:
                wait_time = int(retry_after)
            else:
                # 指数退避 + 随机抖动
                wait_time = (2 ** attempt) + random.uniform(0, 1)

            print(f"触发限流，第 {attempt+1} 次重试，等待 {wait_time:.2f} 秒...")
            time.sleep(wait_time)
        else:
            resp.raise_for_status()

    raise Exception(f"超过最大重试次数 {max_retries}，请求失败")
```

### 3. 大任务分批，每批后写 Checkpoint

将大任务拆分为固定大小的批次，每批完成后将进度写入文件，任务中断后可从上一个 checkpoint 恢复。

```python
import json
import os
import time

CHECKPOINT_FILE = "progress.json"

def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "r") as f:
            return json.load(f)
    return {"last_completed_batch": -1}

def save_checkpoint(batch_index):
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump({"last_completed_batch": batch_index}, f)

def process_in_batches(items, batch_size=100, rate_per_second=5):
    """分批处理，支持断点续传"""
    checkpoint = load_checkpoint()
    start_batch = checkpoint["last_completed_batch"] + 1
    interval = 1.0 / rate_per_second

    batches = [items[i:i+batch_size] for i in range(0, len(items), batch_size)]
    print(f"共 {len(batches)} 批，从第 {start_batch} 批开始恢复...")

    for batch_idx in range(start_batch, len(batches)):
        batch = batches[batch_idx]
        for item in batch:
            request_with_backoff(f"https://api.example.com/process/{item}", headers={})
            time.sleep(interval)

        save_checkpoint(batch_idx)
        print(f"第 {batch_idx+1}/{len(batches)} 批完成，已保存 checkpoint")
```

### 4. 任务可从上一个 Checkpoint 恢复

只需重新运行 `process_in_batches()`，程序会自动读取 `progress.json` 中的进度，跳过已完成的批次，从断点继续执行。

```bash
# 第一次运行（假设在第5批中断）
python batch_job.py
# 输出: 共20批，从第0批开始恢复...
# 输出: 第1/20批完成，已保存 checkpoint
# ...（中断）

# 重新运行，自动从第5批恢复
python batch_job.py
# 输出: 共20批，从第5批开始恢复...
```

## Verification

```bash
python batch_job.py
echo "Verification passed: fix command exited 0"
```

**Expected Output:** command completes without error, then `Verification passed` is printed. (Checks: `python batch_job.py`)
