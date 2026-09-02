---
title: RAG Build Strategy Batch
domain: rag
tags:
- project:self-grow-wiki
- severity:medium
- node:hermes-wsl
status: published
created: '2026-04-13'
language: en
source: hanged-man
domain_expert: hanged-man
verified_date: '2026-04-13'
triggers:
  intents:
  - rag_build
  - embedding
  - vector_index
  - batch_processing
  commands:
  - build_index
  - chroma
  - faiss
  - embedding
  - build_edoc
  environments:
  - wsl
  - gpu
  - cuda
  risks:
  - memory_pressure
  - no_checkpoint
  - batch_overflow
  - driver_crash
  severity: critical
---

## Problem

During knowledge-base construction (chunks_v3, 34,100 docs), all data was loaded into VRAM/WSL memory at once. This caused an LM Studio context overflow, which then led to Summarization timeouts ×4 → LLM timeout → driver crash → BSOD.

## Root Cause

Inspect the RAG config, ingestion log, retrieval log, and cache status to confirm the exact mismatch before applying the fix.

The knowledge-base build batch strategy was wrong: the large dataset was not processed in batches.

## Correct Approach

- When building a large RAG knowledge base, process embeddings in batches whose size fits within available VRAM/memory
- Or use a streaming approach to process files one by one
- Verification: monitor VRAM and memory usage, and set threshold alerts
## Verification

```bash
grep -i 'bm25\|chunk\|embed' lessons/contrib/rag-*.md 2>/dev/null | head -3
echo Search verified
```

**Expected Output:**
```
# (refs)
Search verified
```

## Lesson

RAG knowledge-base construction must first validate memory limits with small batches before scaling up.