---
confidence: '1.0'
created: '2026-06-25'
domain: data
domain_expert: <user>
language: zh
source: <user>
status: published
subdomain: data-pipeline
tags:
- data-pipeline
- dedup
- unique-key
- excel
title: 跨 Sheet 同名合并导致数据混乱：机器人唯一标识必须带前缀
verified_date: '2026-07-06'
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---
## Problem

不同 Excel Sheet（如区域A/区域B）都有同名机器人（如 `R01`），直接按 `robotName` 字段聚合会把不同工位的机器人合并成一台，导致工序序列混乱、统计数据错误。

## Root Cause

`robotName` 在单个 Sheet 内唯一，但跨 Sheet 不唯一。缺乏全局唯一标识时，pandas `groupby('robotName')` 会静默合并同名记录。

## Solution

1. **机器人唯一标识必须带 Sheet 前缀**：`区域A_R01` vs `区域B_R01`
2. 读取多 Sheet 数据时，第一件事是给每条记录打上来源 Sheet 标签
3. 聚合时用 `sheet_prefix + robotName` 作为联合主键

```python
# ❌ 直接按 robotName 合并
for sheet_name, df in sheets.items():
    all_data.append(df)
result = pd.concat(all_data).groupby('robotName').agg(...)

# ✅ 带前缀合并
for sheet_name, df in sheets.items():
    df['robot_id'] = sheet_name + '_' + df['robotName']
    all_data.append(df)
result = pd.concat(all_data).groupby('robot_id').agg(...)
```

## Verification

```bash
echo "Lesson: 跨 Sheet 同名合并导致数据混乱：机器人唯一标识必须带前缀"
wc -l lessons/contrib/cross-sheet-name-merge-data-chaos.md
```

**Expected Output:**
```
Lesson: 跨 Sheet 同名合并导致数据混乱：机器人唯一标识必须带前缀
# (line count)
```
