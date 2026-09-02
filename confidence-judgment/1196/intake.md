---
issue_number: 1196
title: "[Intake] 背景 2026-08-21/22 R-2000iC 换油周期案例：hermes 回答"数值对（碰巧）但来源错位"，④ 误判"KB 蒸馏覆盖缺口"——实际 **B"
score: 38.7
decision: review
created_at: "2026-08-24T07:05:32.854289Z"
---

# [Intake] 背景 2026-08-21/22 R-2000iC 换油周期案例：hermes 回答"数值对（碰巧）但来源错位"，④ 误判"KB 蒸馏覆盖缺口"——实际 **B

**Kind:** missing_lesson
**Source:** remote-agent
**Dedup:** `4399ba36-b6e`

## Problem
## 背景

2026-08-21/22 R-2000iC 换油周期案例：hermes 回答"数值对（碰巧）但来源错位"，④ 误判"KB 蒸馏覆盖缺口"——实际 **B-82334CM/05 §7.3 数据完整在库**（3年/11520h + 指定润滑脂 Alvania S2 + 各轴供脂量 8370ml 等），是**检索漏召回**。同类案例：M-900iB 换油（数据在库但 hermes 答"未覆盖"）。两次都被 LLM 误判为"数据缺失"，根因都在检索层。



## What was tried
harvested from local lesson rag-retrieval-sink-multilayer-cutoff.md

## Fix (if known)
## 修复（四层配合，self-grow-wiki rag_core.py）

1. `_augment_query`：机型保养锚点——查询含 `R-?2000\s*iC` + 换油/润滑/保养词 → 追加 "B-82334CM B-82334EN 润滑脂 更换 定期检修 11520"（BM25 直接命中手册号）
2. RRF 截断 `top_k*2` → `top_k*3`：保 RRF 排名 15-20 的精确答案进候选
3. overlap-guard：手册号锚点命中 chunk 豁免降权 + 加分 0.3（锚点=强匹配信号，`re.findall(r'B-\d{5}[A-Z]{2}', expanded_query)`）
4. diversity：锚点命中 chunk 进 `_exempt` 优先保留（关键——diversity 在 overlap **之前**截断，只改 overl

## Verification
---
{
  "title": "RAG 检索沉底多层机制：同章节措辞差异 + 截断/降权拦截短文本精确答案",
  "tags": ["rag", "retrieval", "silent-degradation", "bm25", "overlap-guard", "fanuc", "anchor"]
}
---

# RAG 检索沉底多层机制：同章节措辞差异 + 截断/降权拦截短文本精确答案

## 背景

2026-08-21/22 R-2000iC 换油周期案例：hermes 回答"数值对（碰巧）但来源错位"，④ 误判"KB 蒸馏覆盖缺口"——实际 **B-82334CM/05 §

---
_Submitted via remote MCP (remote-agent). No account required._
<br/>
<hr/>

<details><summary>This repo is using Opire - what does it mean? 👇</summary><br/>💵 Everyone can add rewards for this issue commenting <code>/reward 100</code> (replace <code>100</code> with the amount).<br/>🕵️‍♂️ If someone starts working on this issue to earn the rewards, they can comment <code>/try</code> to let everyone know!<br/>🙌 And when they open the PR, they can comment <code>/claim #1196</code> either in the PR description or in a PR's comment.<br/><br/>🪙 Also, everyone can tip any user commenting <code>/tip 20 @Ikalus1988</code> (replace <code>20</code> with the amount, and <code>@Ikalus1988</code> with the user to tip).<br/><br/>📖 If you want to learn more, check out our <a href="https://docs.opire.dev">documentation</a>.</details>

