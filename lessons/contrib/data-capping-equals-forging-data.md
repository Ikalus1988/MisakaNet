---
title: 数据封顶=伪造数据：超出阈值应剔除而非截断
domain: data
tags:
- data-quality
- threshold
- capping
- data-integrity
status: published
created: '2026-06-25'
language: zh
source: <user>
confidence: 1.0
domain_expert: <user>
verified_date: '2026-07-06'
subdomain: data-quality
---

## Problem

数据分析中，当数据超出阈值（如实际节拍超过工位节拍），把超出部分"封顶"到阈值值（如写成 100%），本质上是伪造满负荷数据。后续计算基于伪造数据得出错误结论。

封顶操作的危害链条：
- 原始数据异常（Z > P，实际节拍超出目标节拍）
- 封顶后数据看起来"正常"（利用率 = 100%）
- 汇总统计被拉高，掩盖真实产能瓶颈
- 决策者基于失真数据做出错误的产能规划或排班决策
- 问题持续存在但无人察觉，因为数据"看起来没问题"

## Root Cause

封顶和剔除是两种完全不同的操作：
- **封顶** = 把异常值截断到阈值 → 掩盖真实异常，污染后续计算
- **剔除** = 承认数据异常并排除 → 保持数据诚实

"Z > P 封顶 100%"是典型的封顶陷阱：超出阈值的数据被强制拉回阈值，看起来"合理"但完全失真。

深层原因分析：

1. **认知误区**：开发者认为"超出 100% 不合理，所以截断到 100% 是合理修正"。但这混淆了"数据不合理"和"数据应被修正"两个概念——数据不合理恰恰说明它应该被标记和排除，而不是被篡改。

2. **统计污染**：封顶后的数据参与均值、总量等统计计算，会系统性地高估实际利用率。例如 10 条数据中有 3 条被封顶为 100%，即使真实值是 130%、150%、200%，汇总均值也会被人为压低到"看起来合理"的区间。

3. **可追溯性丧失**：封顶后无法区分"真实满负荷（Z = P）"和"异常被截断（Z > P）"，审计和问题排查失去依据。

4. **阈值设计问题**：有时封顶是因为阈值本身设置不合理（过低），正确做法是重新评估阈值，而非用封顶掩盖阈值问题。

## Examples

**具体数字示例：**

假设某工位目标节拍 P = 60 秒，某日 5 条生产记录如下：

| 记录 | 实际节拍 Z | 封顶后利用率 | 剔除后利用率 |
|------|-----------|------------|------------|
| A    | 45s       | 75%        | 75%        |
| B    | 60s       | 100%       | 100%       |
| C    | 72s       | **100%**（伪造） | **None**（剔除） |
| D    | 90s       | **100%**（伪造） | **None**（剔除） |
| E    | 50s       | 83%        | 83%        |

- **封顶口径均值**：(75 + 100 + 100 + 100 + 83) / 5 = **91.6%**（虚高，掩盖了 C、D 的异常）
- **剔除口径均值**：(75 + 100 + 83) / 3 = **86%**（真实，且明确标注有 2 条异常数据被排除）

封顶口径让管理者误以为产线运行良好，而剔除口径则如实反映了 40% 的数据存在异常，需要排查原因。

## Solution

1. **超出阈值的数据直接剔除**（保持空值），不参与后续计算
2. 任何口径都不能"封顶"异常数据
3. 剔除后需记录剔除数量和比例，供审计追溯
4. 如果阈值本身不合理，应调整阈值而非封顶数据
5. 在数据管道入口处统一处理，避免各处重复实现封顶逻辑

```python
# ❌ 封顶 = 伪造
utilization = min(actual_cycle / target_cycle, 1.0)

# ✅ 剔除 = 诚实
if actual_cycle > target_cycle:
    utilization = None  # 标记为异常，不参与统计
else:
    utilization = actual_cycle / target_cycle
```

**批量处理示例（Pandas）：**

```python
import pandas as pd

df = pd.DataFrame({
    'actual_cycle': [45, 60, 72, 90, 50],
    'target_cycle': [60, 60, 60, 60, 60],
})

# ❌ 封顶写法：污染统计
df['utilization_capped'] = (df['actual_cycle'] / df['target_cycle']).clip(upper=1.0)

# ✅ 剔除写法：诚实统计
df['utilization_clean'] = df['actual_cycle'] / df['target_cycle']
df.loc[df['actual_cycle'] > df['target_cycle'], 'utilization_clean'] = None

# 记录剔除情况，供审计
excluded = df['utilization_clean'].isna()
print(f"剔除数量: {excluded.sum()} / {len(df)}，占比: {excluded.mean():.1%}")
# 输出: 剔除数量: 2 / 5，占比: 40.0%

# 仅对有效数据计算均值
valid_mean = df['utilization_clean'].mean()  # 自动忽略 None
print(f"有效数据均值: {valid_mean:.1%}")
# 输出: 有效数据均值: 86.0%
```

**数据管道入口统一校验：**

```python
def compute_utilization(actual_cycle: float, target_cycle: float) -> float | None:
    """
    计算利用率。超出阈值返回 None（剔除），不封顶。
    
    Args:
        actual_cycle: 实际节拍（秒）
        target_cycle: 目标节拍（秒）
    Returns:
        利用率 [0, 1.0]，或 None（异常数据）
    """
    if target_cycle <= 0:
        raise ValueError(f"目标节拍必须为正数，得到: {target_cycle}")
    if actual_cycle > target_cycle:
        return None  # 异常，剔除，不封顶
    return actual_cycle / target_cycle
```

## Verification

```bash
echo "Lesson: 数据封顶=伪造数据：超出阈值应剔除而非截断"
wc -l lessons/contrib/data-capping-equals-forging-data.md
```

**Expected Output:**
```
Lesson: 数据封顶=伪造数据：超出阈值应剔除而非截断
# (line count)
```