---
title: BGE Embedding Fallback Crash
domain: rag
tags:
- project:agent-medici
- severity:high
- node:hermes-wsl
status: published
created: '2026-05-03'
language: en
source: bootstrap
domain_expert: bootstrap
verified_date: '2026-05-03'
subdomain: embedding
---

<!-- provenance:
  contributor: "Ikalus1988"
  merged_at: "2026-05-20"
  evidence: "post-publication"
-->

<!-- 
## Problem

When HermesHub starts, if the BGE-m3 model has not been downloaded to the local path, SkillIndexer crashes immediately.
The local path is hard-coded as `~/.cache/huggingface/...`, which does not exist on other machines.

## Root Cause

Inspect the RAG config, ingestion log, retrieval log, and cache status to confirm the exact mismatch before applying the fix.

`_init_embedding_model()` in `skill_indexer.py` loads the model with `local_files_only=True`, and the model path is a hard-coded machine-specific absolute path. There is no fallback mechanism and no environment-variable override.

## Solution

1. Remove the hard-coded absolute path and use: constructor parameter → `EMBEDDING_MODEL_PATH` environment variable → model name (auto-download)
2. Wrap loading failures in try/except and degrade to no-embedding mode (`register_skill` skips semantic deduplication)
3. Make `_generate_embedding()` return an empty list, so `search_skills` falls back to keyword matching

## Verification

```bash
echo "Lesson: BGE Embedding Fallback Crash"
wc -l lessons/contrib/bge-embedding-fallback-crash.md
```

**Expected Output:**
```
Lesson: BGE Embedding Fallback Crash
# (line count)
```

## Scenario

Any non-development Node machine (Node 1/2/3/6) without a pre-downloaded BGE-m3 model cache.