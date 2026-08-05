---
{
  "title": "RAG Alarm Code Retrieval Needs Mandatory Keyword Recall",
  "domain": "rag",
  "source": "bootstrap",
  "status": "published",
  "tags": [
    "project:self-grow-wiki",
    "severity:high",
    "node:hermes-wsl"
  ],
  "language": "en",
  "created": "2026-05-03",
  "domain_expert": "bootstrap",
  "verified_date": "2026-05-03",
  "subdomain": "fanuc"
}
---

## Problem

When querying "SRVO-023 robot alarm", RAG returned unrelated results instead of the correct FANUC alarm documentation.

## Root Cause

Inspect the RAG config, ingestion log, retrieval log, and cache status to confirm the exact mismatch before applying the fix.

Pure semantic retrieval in ChromaDB has weak discrimination for short codes (SRVO-023, M-900, etc.). Embedding vectors for numeric strings are easily confused with unrelated documents. x"2000" semantically matched both FANUC and KUKA documents.

## Solution

Add keyword mandatory recall to the `retrieve()` function in `rag_core.py`:
1. Alarm code pattern: when `/[A-Z]+-\d+/` matches, forcibly recall documents whose titles/tags contain that code
2. Robot model: match model names (such as M-900 and R-30iB) as strings and merge them into the retrieval results

## Verification

The query "SRVO-023" returns the correct FANUC alarm document list and ranks it near the top. The query "FANUC R-2000iC maximum speed" no longer returns KUKA Series 2000 data.


```bash
# Expected result: retrieval logs show the intended chunks and no stale cache or fallback errors.
python3 search_knowledge.py "rag verification smoke test" --lessons
```

Environment: Linux / WSL with Python 3.10 or newer; adapt the query to the affected RAG corpus.

## Scenario

A FANUC robot knowledge-base RAG system containing many industrial documents with alarm codes and model names.
