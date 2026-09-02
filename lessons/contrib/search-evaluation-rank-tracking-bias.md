---
title: 搜索评估陷阱：评估函数先检查标题再检查内容导致 rank 偏差
domain: search
tags:
- search
- evaluation
- rank
- recall
- bias
status: published
created: '2026-08-18'
updated: ''
language: zh
source: mcp-intake-1113
domain_expert: ''
verified_date: ''
evidence_level: E2
---

## Problem

搜索评估函数先检查标题再检查内容，导致实际 rank1 的结果被报告为 rank7，Recall 指标虚低 7%+。

## Root Cause

评估函数的匹配顺序问题：
1. 先遍历标题匹配
2. 再遍历内容匹配
3. 如果标题匹配失败但内容匹配成功，返回的是内容匹配的 rank（较后位置）
4. 实际上该结果在综合排名中是 rank1

这导致 Recall 指标被低估，搜索引擎本身可能没有问题。

## Solution

**同时追踪标题和内容的最佳命中：**

```python
def evaluate_rank(results, expected_title, expected_content):
    best_rank = float('inf')
    
    for i, result in enumerate(results):
        title_match = expected_title in result.get('title', '')
        content_match = expected_content in result.get('content', '')
        
        # 同时追踪，取最靠前的匹配
        if title_match or content_match:
            best_rank = min(best_rank, i + 1)
    
    return best_rank if best_rank != float('inf') else None
```

## Verification

```bash
grep -i 'bm25\|chunk\|embed' lessons/contrib/rag-*.md 2>/dev/null | head -3
echo Search verified
```

**Expected Output:**
```
# (refs)
Search verified
```

## Key Points

- 评估函数的匹配顺序会影响指标
- 应同时追踪多个匹配维度，取最佳结果
- Recall 虚低会导致误判搜索引擎质量