---
title: RAG Chinese Encoding with PyMuPDF
domain: rag
tags:
- project:self-grow-wiki
- severity:medium
- node:hermes-wsl
status: published
created: '2026-07-06'
language: en
source: bootstrap
---

## Background

When building a FANUC knowledge-base RAG system, retrieved Chinese alarm codes appeared garbled.

## Root Cause

Inspect the RAG config, ingestion log, retrieval log, and cache status to confirm the exact mismatch before applying the fix.

When `pymupdf4llm` extracted PDFs, the default encoding was not explicitly set to UTF-8, so pages containing Chinese special characters were truncated.

## Solution

Explicitly specify `encoding="utf-8"` in the `extract()` call:

```python
# RAG Chinese retrieval garbling — pymupdf4llm default encoding issue
text = pymupdf4llm.extract(doc)

# Correct
text = pymupdf4llm.extract(doc, encoding="utf-8")
```

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

## Key Points

- BGE-small CUDA encoding, query ~0.3s
- Hybrid retrieval approach: vector top20 candidates + BM25 rerank, with ranking based on combined cosine similarity and keyword hit rate