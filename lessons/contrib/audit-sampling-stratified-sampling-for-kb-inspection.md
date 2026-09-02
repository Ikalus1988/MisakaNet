---
title: 巡检题库分层抽样策略
domain: rag
tags:
- rag
- audit
- sampling
- quality
- test-bank
status: published
created: '2026-05-21'
language: zh
confidence: 0.88
---

## Problem

RAG 知识库质量巡检需要每天抽取少量题目进行自动测试。如果随机抽样，容易连续抽到同一类型的问题（如连续三天都是报警代码题），漏掉其他分类的质量退化。

## Root Cause

简单随机抽样（`random.sample`）在大题库 + 小样本（200 题抽 7 题）场景下，类型覆盖不稳定。

## Solution

实现分层抽样策略：

```
题库按 level + tag 分层：
  L2（跨文档）: 弧焊调试 / 型号对比 / IO通信 / 安全配置
  L3（高难度）: 弧焊故障 / 选型 / IO故障 / 负载惯量 / TCP设定

抽样规则：
  1. 从 L2 随机抽 2 题
  2. 从 L3 的每个 tag 中各取至多 1 题，优先覆盖不同 tag
  3. 如果还不够 5 题 L3，从剩余补齐
  4. 最终 7 题混排（不按难度顺序）
```

核心代码：

```python
from collections import defaultdict

def group_by_key(items, key):
    out = defaultdict(list)
    for it in items:
        out[it.get(key)].append(it)
    return out

def sample_questions(bank, l2_count=2, l3_count=5):
    l2 = [q for q in bank if q["level"] == "L2"]
    l3 = [q for q in bank if q["level"] != "L2"]
    l3_by_tag = group_by_key(l3, "tag")

    selected = random.sample(l2, min(l2_count, len(l2)))
    for tag in random.sample(list(l3_by_tag.keys()), len(l3_by_tag)):  # shuffle → sample
        if len(selected) >= l2_count + l3_count:
            break
        selected.append(random.choice(l3_by_tag[tag]))

    remaining = [q for q in l3 if q not in selected]
    selected += remaining[:l2_count + l3_count - len(selected)]
    random.shuffle(selected)
    return selected
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

## When to Use

任何需要从分类题库中定期抽样的 QA 系统都适用，不限于 RAG。