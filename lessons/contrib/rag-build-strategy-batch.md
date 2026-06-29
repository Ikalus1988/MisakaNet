---
domain: "contrib"
title: "rag build strategy batch"
verification: "metadata-normalized"
{"title": "RAG 建库策略：不可一次性加载全部数据到显存/内存", "domain": "rag", "tags": "", "source": "hanged-man", "status": "published", "created": "2026-04-13", "confidence": "0.85", "scope": "broad", "domain_expert": "hanged-man", "verified_date": "2026-04-13"}
---

## Problem

During knowledge-base construction (chunks_v3, 34,100 docs), all data was loaded into VRAM/WSL memory at once. This caused an LM Studio context overflow, which then led to Summarization timeouts ×4 → LLM timeout → driver crash → BSOD.

## Root Cause

The knowledge-base build batch strategy was wrong: the large dataset was not processed in batches.

## Correct Approach

- When building a large RAG knowledge base, process embeddings in batches whose size fits within available VRAM/memory
- Or use a streaming approach to process files one by one
- Verification: monitor VRAM and memory usage, and set threshold alerts
## Verification

1. Follow the solution steps in order
2. Run any relevant commands or tests to confirm the fix
3. Verify the symptom no longer occurs
4. Check related logs or outputs for expected behavior


## Lesson

RAG knowledge-base construction must first validate memory limits with small batches before scaling up.
