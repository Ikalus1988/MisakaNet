---
title: "工艺卡步序提取：辅助动作不算独立步序，按工艺动作分界"
domain: "engineering"
subdomain: "process-analysis"
tags:
  - process-card
  - time-chart
  - sequence
  - cycle-time
  - robot
source: "zsxh1990"
status: "published"
confidence: "0.95"
created: "2026-07-03"
domain_expert: "zsxh1990"
verified_date: "2026-07-06"
---

## Problem

从工艺卡 Time Chart 提取机器人步序时，三种常见错误：
1. 把整个 Time Chart 所有步骤合并成 1 个大序 → CT 偏大
2. 把辅助动作（移到位置、回HOME）完全排除 → 步骤遗漏
3. 用规划节拍推断缺失的步序 → 无中生有

## Root Cause

步序的定义不清晰：**步序 = 工艺动作**（抓件/焊接/涂胶/SPR/拧紧/放件），**辅助动作不算独立步序但计入相邻步序的时间**。

## Solution

### 分组规则

- 辅助动作归入**下一个**工艺动作的步序
- 回HOME归入**最后一个**步序
- 第一个工艺动作吸收前面所有辅助动作

### 示例

```
1. 移到定位夹具  2s  ┐
2. 抓件          8s  ┘→ 1序=10s (移到位置+抓件)
3. 移到固定焊枪  4s  ┐
4. 补焊         12s  ┘→ 2序=16s (移到焊枪+补焊)
5. 移到中转台    4s  ┐
6. 放件          8s  ├→ 3序=14s (移到中转台+放件+回HOME)
7. 回HOME        2s  ┘
```

### 多机器人工位

- 按工位前缀过滤：本工位只保留本工位机器人的步骤
- 排除上游（如 `上游工位-R02放件`）和下游（如下游工位-R01抓件）
- 每个机器人的步序填到对应的行

### 铁律

工艺卡 Time Chart 中没有的机器人步序，不能推断、不能补填。

## Verification

```python
# 验证：所有工艺动作都被统计
process_actions = ['抓件', '放件', '焊接', '涂胶', 'SPR', '拧紧', '滚床']
extracted = [s['name'] for s in sequences]
for action in process_actions:
    if any(action in step for step in all_steps):
        assert any(action in e for e in extracted), f"{action} 未被提取为步序"
```
