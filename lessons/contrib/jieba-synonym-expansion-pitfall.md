---
{
  "title": "同义词扩展陷阱：jieba.add_word() 改变全局分词行为导致回归",
  "domain": "search",
  "tags": ["jieba", "synonym", "chinese", "segmentation", "regression"],
  "status": "published",
  "evidence_level": "E2",
  "source": "mcp-intake-1114",
  "created": "2026-08-18",
  "updated": "",
  "verified_date": "",
  "domain_expert": ""
}

provenance:
  source: "unknown"
  contributor: "Ikalus1988"
  merged_at: "2026-08-18"
  evidence: "post-publication"
---

## Problem

使用 jieba.add_word() 添加同义词时，会改变全局分词行为，导致其他查询回归。

## Root Cause

jieba.add_word() 的问题：
1. 改变全局分词器状态，影响所有后续查询
2. 新词优先级高于已有分词规则
3. 语义扩展（如"手机"→"电话"）不适合用 add_word
4. 只有专有名词才应该用 add_word

## Solution

**用同义词映射文件代替 add_word：**

```python
# 错误方式：改变全局分词
jieba.add_word("手机")  # 会影响所有查询

# 正确方式：同义词映射文件
# synonyms.json:
{
  "手机": ["电话", "移动设备", "智能手机"],
  "电脑": ["计算机", "PC", "笔记本"]
}

def expand_query_with_synonyms(query, synonyms):
    expanded = [query]
    for word, syns in synonyms.items():
        if word in query:
            expanded.extend(syns)
    return expanded
```

**规则：**
- 只有专有名词才用 add_word（如产品名、品牌名）
- 语义扩展必须用映射文件
- 映射文件可版本控制，可审计
- add_word 改变全局状态，不可控

## Verification

- 修复后其他查询无回归
- 同义词扩展生效（"手机"搜索能匹配"电话"相关内容）
- 专有名词仍可用 add_word

## Key Points

- jieba.add_word() 改变全局分词行为，不可控
- 语义扩展必须用同义词映射文件
- 只有专有名词才用 add_word
- 映射文件可版本控制、可审计
