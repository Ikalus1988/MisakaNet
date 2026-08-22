---
{
  "title": "中文 BM25 搜索：滑动窗口子串加分与唯一候选加分",
  "domain": "search",
  "tags": [
    "bm25",
    "chinese",
    "search",
    "recall",
    "sliding-window"
  ],
  "status": "published",
  "evidence_level": "E2",
  "source": "pr",
  "created": "2026-08-18",
  "updated": "",
  "verified_date": "",
  "domain_expert": "",
  "author": "Ikalus1988",
  "edited_at": "2026-08-18T12:06:05+08:00",
  "merged_by": "Ikalus1988",
  "pr": 1114
}
---

## Problem

中文 BM25 搜索长查询召回率低，标准 BM25 对中文分词后的短 token 敏感度不足。

## Root Cause

1. 中文查询经 jieba 分词后产生短 token（2-3字），BM25 对短 token 的 IDF 权重不够
2. 稀有词（仅匹配1个文档）的 IDF 没有额外加权
3. 全局 DF 表缺失词的 IDF 回退策略不当

## Solution

**滑动窗口子串加分：**
- 对 4-6 字的子串窗口进行额外加分
- 设置 10 字门槛防止噪声（太短的子串不加分）
- 提升长查询中连续语义片段的召回

**唯一候选加分：**
- 当一个词仅匹配 1 个文档时，IDF × 2.0
- 限制仅对纯中文词生效，避免英文回归
- 提升稀有专有名词的精确匹配

```python
# 滑动窗口加分示例
def sliding_window_boost(query, doc, window_min=4, window_max=6, threshold=10):
    if len(query) < threshold:
        return 0
    boost = 0
    for w in range(window_min, window_max + 1):
        for i in range(len(query) - w + 1):
            substring = query[i:i+w]
            if substring in doc:
                boost += 1
    return boost

# 唯一候选加分示例
def unique_candidate_boost(df, doc_freq, is_chinese=True):
    if not is_chinese:
        return 1.0  # 英文不加分
    if doc_freq == 1:
        return 2.0  # 仅匹配1个文档，IDF翻倍
    return 1.0
```

## Verification

- Recall 指标提升 7%+
- 英文查询无回归（唯一候选仅对纯中文词生效）
- 滑动窗口在 10 字以下查询不触发（防噪声）

## Key Points

- 滑动窗口需设 10 字门槛防噪声
- 唯一候选需限制纯中文词防英文回归
- 全局 DF 表缺失词需要 IDF 回退策略
