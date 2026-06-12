---
{"title": "Systematic Debugging", "domain": "general", "source": "skill-pipeline", "status": "draft", "tags": [], "created": "2026-05-09", "updated": "2026-05-09"}
---


## 背景

（此 lesson 从 skill `systematic-debugging` 自动提取，待补全）

## 根因

（待补充）

## 修复


# Systematic Debugging

## Overview

Random fixes waste time and create new bugs. Quick patches mask underlying issues.

**Core principle:** ALWAYS find root cause before attempting fixes. Symptom fixes are failure.

**Violating the letter of this process is violating the spirit of debugging.**

## The Iron Law

```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

If you haven't completed Phase 1, you cannot propose fixes.

## When to Use

Use for ANY technical issue:
- Test failures
- Bugs in production
- Unexpected behavior
- Performance problems
- Build failures
- Integration issues
- **Silent failures — systems that "run" but produce no value** (no errors, no crashes, just zero output)

**Use this ESPECIALLY when:**
- Under time pressure (emergencies make guessing tempting)
- "Just one quick fix" seems obvious
- You've already tried multiple fixes
- Previous fix didn't work
- You don't fully understand the issue
- **Everything "seems fine" but nothing is happening** — no errors, just no results (this is the most dangerous type of failure because it creates the illusion of a working system)

**Don't skip when:**
- Issue seems simple (simple bugs have root causes too)
- You're in a hurry (rushing guarantees rework)
- Someone wants it fixed NOW (systematic is faster than thrashing)

## The Four Phases

You MUST complete each phase before proceeding to the next.

---

## Phase -1: 知识检索（硬性门禁）

> 在开始根因分析之前，先确认现有知识库中是否已有同类问题的分析记录。
> 虫群 lessons/reference 中可能已有其他节点解决的类似问题。

### Step -1.1: 搜索 lessons 和 reference

用当前报错/异常的关键词检索知识库：

```bash
cd ~/Agent-Medici
python3 search_knowledge.py "<核心错误关键词>" --lessons
python3 search_knowledge.py "<组件名/工具名>" --ref
```

搜索词应包括：
- 核心错误信息（如 "connection refused"、"timeout"、"exit code 1"）
- 涉及组件名（Hermes、Gateway、ChromaDB、WSL、cc-haha 等）
- 项目名（Agent-Medici、MisakaNet、self-grow-wiki 等）

**Output gate：** 输出命中数量 + top-3 文件的实际摘要。如果 search_knowledge.py 返回空，输出 `"search_knowledge.py 空结果"` 并补充手动 `grep -r "关键词" lessons/`。

### Step -1.2: 输出检索结论

```
📋 检索结论
  - 可复用的 lessons: [标题列表]
  - 可复用的 reference: [文件名列表]
  - 与当前调试任务的关系: [这些知识能直接复用，还是只是背景参考]
  - 核心风险（如果不检索会犯什么错）: [一句话]
```

**Output gate：** 必须输出此结论块。不输出 = 不允许进入 Phase 0/1。

---

## Phase 0: Silent Failure Probe

**WHEN there are no errors but the system isn't producing value:**

This is the most insidious failure mode. Pipelines execute, logs rotate, `ps aux` shows processes — but nothing useful comes out. Users feel the system is "dead" but can't point to a specific error.

**Do NOT start fixing. Start measuring.**

### Step 0.1: Define "What Does Success Look Like?"

Before touching anything, define the system's **output contract**:
- What is the system supposed to produce? (lessons, reports, alerts, query results)
- What is "one unit of value"? (one written lesson, one notification sent)
- What is the minimum expected frequency? (per day, per hour, per cron tick)

### Step 0.2: Measure Actual Output

For each pipeline/product path, gather hard data:

```bash
# Example: how

## 验证

（待补充）
