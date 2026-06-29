---
domain: "contrib"
title: "RAG 检索中文乱码 — pymupdf4llm 默认编码Issue"
verification: "metadata-normalized"
---
---{"title": "RAG 检索中文乱码 — pymupdf4llm 默认编码Issue", "domain": "rag", "source": "bootstrap", "status": "published", "confidence": "0.7", "created": "2026-04-01"}---


## Background

When building a FANUC knowledge-base RAG system, retrieved Chinese alarm codes appeared garbled.

## Root Cause

When `pymupdf4llm` extracted PDFs, the default encoding was not explicitly set to UTF-8, so pages containing Chinese special characters were truncated.

## Fix

Explicitly specify `encoding="utf-8"` in the `extract()` call:

```python
# RAG Chinese retrieval garbling — pymupdf4llm default encoding issue
text = pymupdf4llm.extract(doc)

# Correct
text = pymupdf4llm.extract(doc, encoding="utf-8")
```

## Verification

Re-import PDFs containing Chinese alarm codes (for example, SRVO-023); retrieval returns the correct Chinese descriptions.

## Key Points

- BGE-small CUDA encoding, query ~0.3s
- Hybrid retrieval approach: vector top20 candidates + BM25 rerank, with ranking based on combined cosine similarity and keyword hit rate
