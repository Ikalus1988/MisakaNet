---
title: "跨 Sheet 同名合并导致数据混乱：机器人唯一标识必须带前缀"
domain: "data"
subdomain: "data-pipeline"
tags:
  - data-pipeline
  - dedup
  - unique-key
  - excel
source: "zsxh1990"
status: "published"
confidence: "1.0"
created: "2026-06-25"
domain_expert: "zsxh1990"
verified_date: "2026-07-06"
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

```python
# 验证：合并后 robot_id 应该与原始记录数一致
assert len(result) == len(pd.concat(all_data)['robot_id'].unique())
# 验证：检查是否有同名不同 Sheet 的机器人
name_counts = pd.concat(all_data).groupby('robotName')['robot_id'].nunique()
duplicates = name_counts[name_counts > 1]
if len(duplicates) > 0:
    print(f"⚠️ {len(duplicates)} 个机器人在多个 Sheet 中同名")
```
