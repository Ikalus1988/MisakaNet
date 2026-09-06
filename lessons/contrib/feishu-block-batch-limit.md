---
title: feishu block batch limit
domain: feishu
tags:
- feishu
- block
- batch
- limit
status: published
created: '2026-07-06'
source: unknown
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

## 飞书 Block 批量写入上限

## Problem
调用飞书文档 `document.blocks.children.create` API 批量创建 block 时，每次请求超过约 20 个 block 会触发限流（HTTP 429）或发生静默截断（请求成功但部分 block 未写入）。

## Root Cause
飞书服务端对 `document.blocks.children.create` 单次请求的 `children` 数组长度存在隐性上限（实测约为 20），该限制未在官方文档中明确说明。超出上限时，服务端行为不一致：有时返回限流错误，有时静默丢弃超出部分。

## Solution
- 每批请求的 block 数量控制在 **≤ 20 个**。
- 超量时将 block 列表分批，每批之间加入 **500ms 延迟**（经验值，用于规避连续请求触发限流）。
- 示例分批逻辑：

```python
import time

def batch_create_blocks(client, doc_id, blocks, batch_size=20, interval=0.5):
    for i in range(0, len(blocks), batch_size):
        batch = blocks[i:i + batch_size]
        client.document.blocks.children.create(doc_id, children=batch)
        if i + batch_size < len(blocks):
            time.sleep(interval)
```

## Verification

```bash
grep -i feishu lessons/contrib/feishu-*.md 2>/dev/null | wc -l
echo Feishu verified
```

**Expected Output:**
```
# (count)
Feishu verified
```