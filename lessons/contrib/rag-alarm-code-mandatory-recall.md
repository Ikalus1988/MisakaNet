---
domain: "contrib"
title: "rag alarm code mandatory recall"
verification: "metadata-normalized"
{"title": "RAG 报警代码检索需要关键词强制召回", "domain": "rag", "subdomain": "fanuc", "source": "bootstrap", "status": "draft", "tags": ["project:self-grow-wiki", "severity:high", "node:hermes_wsl"], "confidence": "0.8", "created": "2026-05-03", "domain_expert": "bootstrap", "verified_date": "2026-05-03"}
---

## Problem

When querying "SRVO-023 robot alarm", RAG returned unrelated results instead of the correct FANUC alarm documentation.

## Root Cause

Pure semantic retrieval in ChromaDB has weak discrimination for short codes (SRVO-023, M-900, etc.). Embedding vectors for numeric strings are easily confused with unrelated documents. x"2000" semantically matched both FANUC and KUKA documents.

## Fix

Add keyword mandatory recall to the `retrieve()` function in `rag_core.py`:
1. Alarm code pattern: when `/[A-Z]+-\d+/` matches, forcibly recall documents whose titles/tags contain that code
2. Robot model: match model names (such as M-900 and R-30iB) as strings and merge them into the retrieval results

## Verification

The query "SRVO-023" returns the correct FANUC alarm document list and ranks it near the top. The query "FANUC R-2000iC maximum speed" no longer returns KUKA Series 2000 data.

## Scenario

A FANUC robot knowledge-base RAG system containing many industrial documents with alarm codes and model names.
