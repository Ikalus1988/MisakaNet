---
{
  "title": "RAG Chinese Encoding with PyMuPDF",
  "domain": "rag",
  "source": "bootstrap",
  "status": "draft",
  "language": "en",
  "tags": [
    "project:self-grow-wiki",
    "severity:medium",
    "node:hermes-wsl"
  ]
}
---



## Background

When building a FANUC knowledge-base RAG system, retrieved Chinese alarm codes appeared garbled.

## Root Cause

Inspect the RAG config, ingestion log, retrieval log, and cache status to confirm the exact mismatch before applying the fix.

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


```bash
# Expected result: retrieval logs show the intended chunks and no stale cache or fallback errors.
python3 search_knowledge.py "rag verification smoke test" --lessons
```

Environment: Linux / WSL with Python 3.10 or newer; adapt the query to the affected RAG corpus.

## Key Points

- BGE-small CUDA encoding, query ~0.3s
- Hybrid retrieval approach: vector top20 candidates + BM25 rerank, with ranking based on combined cosine similarity and keyword hit rate
