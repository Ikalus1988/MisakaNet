---
title: RAG 检索沉底多层机制：同章节措辞差异 + 截断/降权拦截短文本精确答案
domain: rag
tags:
- rag
- retrieval
- silent-degradation
- bm25
- overlap-guard
- fanuc
- anchor
status: published
created: '2026-08-24'
language: zh
source: intake-issue-1196
evidence_level: E2
---

## Problem

2026-08-21/22 R-2000iC 换油周期案例：hermes 回答"数值对（碰巧）但来源错位"，④ 误判"KB 蒸馏覆盖缺口"——实际 **B-82334CM/05 §7.3 数据完整在库**（3年/11520h + 指定润滑脂 Alvania S2 + 各轴供脂量 8370ml 等），是**检索漏召回**。同类案例：M-900iB 换油（数据在库但 hermes 答"未覆盖"）。两次都被 LLM 误判为"数据缺失"，根因都在检索层。

## Root Cause

多层检索管道各自丢弃精确答案 chunk，无单一修复足够：

1. **查询措辞差异** — 用户问"换油周期"，手册用"润滑脂更换/定期检修"，BM25 与向量均未命中手册号
2. **RRF 截断过紧** — `top_k*2` 在 RRF 排名 15–20 的精确 chunk 被截掉
3. **overlap-guard 降权** — 短文本精确答案因与查询词重叠低被降权沉底
4. **diversity 提前截断** — diversity 在 overlap-guard 之前截断，锚点命中 chunk 未获优先保留

## Solution

四层配合修复（`self-grow-wiki` 的 `rag_core.py`）：

### 1. `_augment_query`：机型保养锚点

查询含 `R-?2000\s*iC` + 换油/润滑/保养词时，追加手册号锚点：

```python
if re.search(r'R-?2000\s*iC', query, re.I) and re.search(r'换油|润滑|保养', query):
    query += " B-82334CM B-82334EN 润滑脂 更换 定期检修 11520"
```

BM25 直接命中手册号，绕过措辞差异。

### 2. RRF 截断放宽

`top_k*2` → `top_k*3`，保留 RRF 排名 15–20 的精确答案进入候选池。

### 3. overlap-guard：手册号锚点豁免

手册号锚点命中的 chunk 豁免降权并加分 0.3：

```python
anchors = re.findall(r'B-\d{5}[A-Z]{2}', expanded_query)
for chunk in candidates:
    if any(a in chunk.text for a in anchors):
        chunk.score += 0.3  # 锚点 = 强匹配信号，豁免降权
```

### 4. diversity：锚点 chunk 优先保留

锚点命中的 chunk 加入 `_exempt` 集合，在 diversity 截断时优先保留（diversity 在 overlap-guard 之前执行，只改 overlap 不够）。

## Verification

```bash
python3 search_knowledge.py "R-2000iC 换油周期 B-82334" --lessons
grep -c "B-82334" lessons/contrib/rag-retrieval-sink-multilayer-cutoff.md
```

**Expected:** lesson 可被检索到；grep 返回 ≥1。

## Key Points

- 数据在库但检索漏召回时，LLM 会误判为"KB 覆盖缺口"——先查检索层再查蒸馏层
- 手册号（如 `B-82334CM`）是强锚点，应贯穿 query 扩展、RRF 截断、overlap-guard、diversity 四层
- 与 [rag-retrieval-six-layer-silent-degradation](rag-retrieval-six-layer-silent-degradation.md) 互补：该 lesson 覆盖 M-900iB 六层退化，本 lesson 聚焦 FANUC 保养手册号的四层锚点修复

## Related Lessons

- rag-retrieval-six-layer-silent-degradation: M-900iB 六层静默退化
- fanuc-r-2000ic-retrieval-fix: R-2000iC 跨品牌型号混淆的关键词强制召回
