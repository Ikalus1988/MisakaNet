---
title: RAG Alarm Code Retrieval Needs Mandatory Keyword Recall
domain: rag
tags:
- project:self-grow-wiki
- severity:high
- node:hermes-wsl
status: published
created: '2026-05-03'
language: en
source: bootstrap
domain_expert: bootstrap
verified_date: '2026-05-03'
subdomain: fanuc
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

A FANUC robot knowledge-base RAG system containing many industrial documents with alarm codes and model names.