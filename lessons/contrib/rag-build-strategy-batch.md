---
{
  "title": "RAG Build Strategy Batch",
  "domain": "rag",
  "source": "hanged-man",
  "status": "published",
  "tags": [
    "project:self-grow-wiki",
    "severity:medium",
    "node:hermes-wsl"
  ],
  "language": "en",
  "created": "2026-04-13",
  "domain_expert": "hanged-man",
  "verified_date": "2026-04-13"
}
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

1. Follow the solution steps in order
2. Run any relevant commands or tests to confirm the fix
3. Verify the symptom no longer occurs
4. Check related logs or outputs for expected behavior



```bash
# Expected result: retrieval logs show the intended chunks and no stale cache or fallback errors.
python3 search_knowledge.py "rag verification smoke test" --lessons
```

Environment: Linux / WSL with Python 3.10 or newer; adapt the query to the affected RAG corpus.

## Lesson

RAG knowledge-base construction must first validate memory limits with small batches before scaling up.
