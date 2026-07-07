---
title: Agent Memory Three-Index Architecture on Elasticsearch
domain: agent
subdomain: memory
tags:
- agent-memory
- elasticsearch
- episodic
- semantic
- procedural
- hybrid-retrieval
- rrf
source: elastic.co/search-labs
status: published
confidence: '0.9'
created: '2026-07-01'
verified_date: ''
domain_expert: elastic
---


## Problem

Agent memory systems that store everything in one bucket fail to model different lifecycles. Episodic events (high write, time-decay), semantic facts (low write, supersede on contradiction), and procedural playbooks (low write, outcome feedback) have incompatible update and aging rules.

## Root Cause

Cognitive science (Tulving 1972) identifies three memory types with distinct properties. Engineering implementations that use one storage for all three force awkward compromises on write rate, aging, and update semantics.

## Solution

### Three Indices, One Per Memory Type

| Type | Write Rate | Aging | Update Rule |
|------|-----------|-------|-------------|
| **Episodic** | High (every user message) | Time decay | Append only, never update |
| **Semantic** | Low (after extraction) | No decay | Supersede on contradiction (keep audit trail) |
| **Procedural** | Low | No decay | success_count / failure_count increment |

### Hybrid Recall Pipeline

```
Query → BM25 + Vector search → RRF fusion → cross-encoder reranker → Top-K
```

### Supersession (Not Deletion)

When a user contradicts a recalled fact, mark the old version as superseded by the new one. Never delete — preserve the audit trail.

### User Isolation

Use Document Level Security (DLS) to ensure each user's memory is invisible to every other user.

## Verification

1. R@10 = 0.89 on 168-question QA eval
2. Zero cross-tenant leaks
3. Supersession preserves full history

## Notes

- "1M token context window is a scratchpad, not a memory system"
- Context window = short-term memory; missing is long-term memory
- Full implementation: github.com/elastic/agent-builder
- Source: https://www.elastic.co/search-labs/blog/agent-memory-elasticsearch
