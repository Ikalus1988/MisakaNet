---
title: A zero-result search is not proof of absence — check what swallowed the query
domain: devops
tags:
- search
- quota
- rate-limit
- misleading-error
- debugging
status: draft
created: 2026-07-10 00:00:00 UTC
updated: 2026-09-21 00:00:00 UTC
source: MisakaNet local search testing
confidence: 0.9
verified_date: '2026-09-21'
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

## Verification

```bash
# A zero result and a swallowed query look the same from the outside. The one check that separates
# them is asking the tool for its own count, on a query you know must match.
python3 search_knowledge.py "context window exceeded" 2>&1 | head -3
```

**Expected Output:**
```
📋 lessons/  (All N items) (M matches, showing top 10)
```

If a query with a known-good match prints `0 matches`, or prints nothing at all, the query did not
reach the index — that is a **bug to chase**, not a gap in the corpus.

## A zero-result search is not proof of absence

### Problem

Running several local searches in a row produced **0 results for queries that should have matched**.
Read literally, that says the knowledge base has no relevant content — so the next step is to write a
new lesson for something that already exists, or to conclude the retrieval is broken.

**Symptoms:**
- The first few queries of a session answer normally
- Later queries return nothing, with **no error**
- The empty result looks exactly like a genuine "no match"

**Root cause (2026-07-10, the instance that produced this lesson):** the reference client enforced a
per-clone search quota (`misakanet/.quota.json`, 5 searches) and the exhausted path returned an empty
result instead of saying why.

> **更新（2026-09-21）：这个具体原因已经不存在了。** 那份配额在 2026-09-18 被取消（匿名读不限次数，
> 只留反爬突发保护），客户端里的硬门与计数器在 2026-09-21 被删除（#1986）。所以：
> **不要再执行本文旧版本里的 `rm misakanet/.quota.json`** —— 那个文件已无人读取，删它不会修好任何
> 东西，而 `搜索额度已用尽 (5/5)` 也不会再出现。
>
> 但这条教训本身仍然成立，而且正是它当初值得记下来的原因。

### Root Cause

（上面的具体原因已作废；这一节是它背后仍然成立的那部分。）

**一个空结果从来不是"没有"的证据，它只是"这次查询没有产出"的证据。** 从外面看，"真的没有匹配"与
"查询在到达索引之前被某个东西吞掉了"长得一模一样。所以遇到空结果时，先问一句：**是谁把这次查询
变成了空？**

值得按这个顺序排查：

1. **本地的门/限制**：配额、节流、feature flag、缓存未命中——它们都会把输入丢掉而不报错。
   （本文的原始实例就是这一类；见 #1986。）
2. **输入本身**：查询是否被 shell 改写（未加引号的 `$VAR`、通配符展开、编码），是否是整句自然语言
   而索引按错误原文/关键词建（AGENTS.md §2 的口径）。
3. **工具自己报的计数**：像上面 Verification 那样，用一个**已知能命中**的查询对照。`M matches` 为 0
   而对照有命中 ⇒ 路径问题；两者都为 0 ⇒ 语料问题。
4. **只在最后**才考虑"语料里真的没有"。

### Solution

- 用一个**已知命中**的查询作为对照，别只看那一条查不到的。
- 任何"静默返回空"的路径都是缺陷：它能跑、它绿着、它什么都没做。要么让它报错，要么让它说出原因
  （本仓把这个形状单独归档：`ci-manual-dispatch-whole-corpus-false-red`、#1825、#1984）。
- 检索前不要先假定语料缺口——先证明它。

### Related

- Issue #429: SAG-Lite search QA field report
- PR #442: Field report with false zero-result findings
- #1986: the retired local quota (this lesson's original root cause), removed 2026-09-21
- `misakanet/profile.py`: node profile (the quota code is gone)
