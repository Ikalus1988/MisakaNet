---
domain: "contrib"
title: "bge embedding fallback crash"
verification: "metadata-normalized"
{"title": "BGE embedding 模型需要降级 fallback 避免启动崩溃", "domain": "rag", "subdomain": "embedding", "source": "bootstrap", "status": "draft", "tags": ["project:agent-medici", "severity:high", "node:hermes_wsl"], "confidence": "0.8", "created": "2026-05-03", "domain_expert": "bootstrap", "verified_date": "2026-05-03"}
---

## Problem

When HermesHub starts, if the BGE-m3 model has not been downloaded to the local path, SkillIndexer crashes immediately.
The local path is hard-coded as `~/.cache/huggingface/...`, which does not exist on other machines.

## Root Cause

`_init_embedding_model()` in `skill_indexer.py` loads the model with `local_files_only=True`, and the model path is a hard-coded machine-specific absolute path. There is no fallback mechanism and no environment-variable override.

## Fix

1. Remove the hard-coded absolute path and use: constructor parameter → `EMBEDDING_MODEL_PATH` environment variable → model name (auto-download)
2. Wrap loading failures in try/except and degrade to no-embedding mode (`register_skill` skips semantic deduplication)
3. Make `_generate_embedding()` return an empty list, so `search_skills` falls back to keyword matching

## Verification

Start the hub on a machine without the BGE-m3 model. It does not crash and prints "[Embedding] degraded mode — semantic deduplication and search will be unavailable".

## Scenario

Any non-development Node machine (Node 1/2/3/6) without a pre-downloaded BGE-m3 model cache.
