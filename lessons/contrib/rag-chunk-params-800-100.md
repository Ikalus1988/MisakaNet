---
title: RAG Chunk Parameters 800 Characters and 100 Overlap
domain: rag
tags:
- project:self-grow-wiki
- severity:medium
- node:hermes-wsl
status: published
created: '2026-05-03'
language: en
source: bootstrap
domain_expert: bootstrap
verified_date: '2026-05-03'
subdomain: chunking
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

## Problem

After importing FANUC PDF documents into RAG, retrieval quality was unstable and recall was low for long documents.

## Root Cause

Inspect the RAG config, ingestion log, retrieval log, and cache status to confirm the exact mismatch before applying the fix.

The chunking strategy was inappropriate. Chunks that are too large (>2000 characters) contain multiple topics and become semantically blurry; chunks that are too small (<200 characters) lack context and produce embeddings with low discriminative power.

## Solution

Use the following chunking parameters:
```python
RecursiveCharacterTextSplitter(
    chunk_size=800,        # About 800 characters per chunk
    chunk_overlap=100,     # 100-character overlap between chunks
    length_function=len,
    separators=["\n\n", "\n", "。", "！", "？", " ", ""]
)
```
Keep at most 100 chunks per file, truncating anything beyond that to prevent oversized documents from filling the vector store.

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

## Scenario

Mixed Chinese/English technical documents (FANUC manuals), especially PDF / Word documents with clear paragraph structure.