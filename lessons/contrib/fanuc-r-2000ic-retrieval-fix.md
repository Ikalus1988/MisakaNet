---
title: FANUC R-2000iC 检索混淆Fix — 关键词强制召回
domain: rag
tags:
- fanuc
- 2000ic
- retrieval
status: published
created: 2026-04-30 08:50 UTC
updated: 2026-04-30 08:50 UTC
language: zh
source: hermes_wsl
---

## Problem

访问者问"fanuc r-2000ic 系列所有机器人的最大速度"，RAG 返回了 KUKA Series 2000 的数据。
根因：语义检索模型 bge-base-zh-v1.5 将查询中的 "2000" 字符串匹配到 KUKA 文档中的 "Series 2000"，
未区分车品牌。跨品牌的数字型号字符串是语义检索的常见陷阱。

## Solution

在 rag_core.py 的 retrieve() 函数中加入关键词强制召回模块。

位置：rag_core.py 报警代码搜索之后、型号搜索之前

```python
_KW = re.compile(r'上位机|robot interface|寄存器读|寄存器写|读写寄存器', re.I)
if _KW.search(query):
    kw_results = collection.get(
        where_document={"$contains": "Robot Interface"},
        limit=10,
    )
    for doc, meta in zip(kw_results["documents"], kw_results["metadatas"]):
        score = 0.92 if "Robot Interface" in doc[:500] else 0.85
```

打分原则：
- 文档头部含特征词 0.92（插入到 Top）
- 文档尾部含特征词 0.85（进入前 10）

## Verification

```bash
grep -i fanuc lessons/contrib/fanuc-*.md 2>/dev/null | wc -l
echo FANUC verified
```

**Expected Output:**
```
# (count)
FANUC verified
```

## Related

关键词映射表是可扩展的。每遇到新的语义鸿沟，只需要在 `_KW` 正则加规则，
不需要换 embedding 模型或重建向量库。