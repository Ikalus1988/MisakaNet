---
title: Cross-encoder reranker kills RAG latency on CPU-only machines
domain: rag
subdomain: reranking
tags: ["rag", "cross-encoder", "reranking", "cpu-bottleneck", "latency", "bge-reranker", "performance"]
status: published
confidence: 0.9
created: 2026-07-06
updated: 2026-07-06
source: zsxh1990
verified_date: 2026-07-06
---

# Cross-encoder reranker kills RAG latency on CPU-only machines

## Problem

RAG knowledge-base queries take 40-60 seconds on CPU-only infrastructure.
Cold start is 110+ seconds. Warm queries still take 40+ seconds.
The same question produces different answers across calls.

Breakdown of a typical warm query:

| Stage | Time |
|-------|------|
| Vector retrieval (embedding + ANN) | 0.3s |
| BM25 keyword search | 0.1s |
| Entity exact match | 0.05s |
| LLM generation | 1.5s |
| **Cross-encoder reranking** | **42.7s** |
| **Total** | **~44s** |

The reranker accounts for 97% of query latency.

## Root Cause

### Speed: cross-encoder on CPU

`BAAI/bge-reranker-v2-m3` (568M parameters) performs pairwise inference:
for each of the 25 candidate documents, it encodes the (query, document) pair
through the full transformer, then scores relevance.

On GPU: ~10ms per pair → 250ms total.
On CPU: ~1.5s per pair → 37-60s total.

This was hidden because no timing logs existed for the reranking stage.
The initial guess was "ChromaDB overhead" — wrong. Adding `[TIMING]` instrumentation
revealed the reranker was the sole bottleneck.

### Inconsistency: temperature + no seed

Three factors combined:
1. `temperature=0.3` allows sampling randomness
2. No `seed` parameter → each LLM call uses a different random state
3. `share_session_in_channel=true` in group chat → multiple users share one session, polluting context

## Solution

### 1. Disable cross-encoder reranking

The existing ranking signals (RRF fusion of vector + BM25, entity match, tag boost)
are sufficient for most use cases. Cross-encoder reranking adds marginal precision
at enormous CPU cost.

```python
# Option A: config override
RERANK_TOP_K = 0  # skip reranking entirely

# Option B: return None from factory
def get_reranker():
    return None
```

**Result**: warm query 44s → ~1.2s. Cold start 34s → ~2s.

### 2. If you need reranking, use a lightweight model on GPU

```python
# Switch to a smaller model (~100M params vs 568M)
from sentence_transformers import CrossEncoder

reranker = CrossEncoder(
    "BAAI/bge-reranker-v2-minicpm-layerwise",
    device="cuda",  # must be GPU
    max_length=512,
)
scores = reranker.predict([(query, doc) for doc in candidates])
```

CPU-only? Use a bi-encoder reranker instead (no pairwise encoding):

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("BAAI/bge-small-en-v1.5")  # 33M params
query_emb = model.encode(query)
doc_embs = model.encode(candidates)
scores = query_emb @ doc_embs.T  # cosine similarity, ~50ms on CPU
```

### 3. Fix answer consistency

```python
kwargs = dict(
    model=model_id,
    messages=messages,
    temperature=0,      # deterministic
    seed=42,            # fixed seed
    top_p=1,            # disable nucleus sampling
    max_tokens=4096,
    stream=True,
)
```

The trio `temperature=0 + seed=42 + top_p=1` is required for deterministic output.
Some API implementations still vary with `temperature=0` alone if no seed is set.

### 4. Isolate group chat sessions

```toml
# Bot config
[projects.platforms.options]
share_session_in_channel = false  # per-user sessions
```

## Verification

### Test 1: Latency

```bash
# Before: expect 40-60s
time python3 search_knowledge.py "database connection timeout" --top=5

# After disabling reranker: expect <2s
time python3 search_knowledge.py "database connection timeout" --top=5
```

### Test 2: Consistency

```bash
# Run the same query 3 times, compare outputs
for i in 1 2 3; do
  python3 search_knowledge.py "slow query optimization" --top=3
done
# Expected: identical results every time (with temperature=0 + seed=42)
```

### Test 3: Ranking quality

```bash
# Compare top-5 results with and without reranker
python3 search_knowledge.py "redis cache eviction policy" --top=5
# Spot check: are the top results still relevant?
# In most cases, RRF fusion produces comparable ranking quality.
```

## Notes

- Cross-encoder reranking is valuable when you have <10 candidates and need precise ordering (e.g., legal search, medical QA). For general RAG with 25+ candidates from diverse retrieval methods, the marginal gain rarely justifies the CPU cost.
- Bi-encoder reranking (cosine similarity on embeddings) is a middle ground: 10-100x faster than cross-encoder on CPU, with 80-90% of the ranking quality.
- Always add `[TIMING]` instrumentation to every pipeline stage before optimizing. Guessing the bottleneck wastes time.

## Environment

- Platform: Linux (WSL2), CPU-only (no GPU)
- Python: 3.10+
- Models: `BAAI/bge-reranker-v2-m3` (568M), `BAAI/bge-reranker-v2-minicpm-layerwise` (100M)
- Vector DB: ChromaDB / FAISS
- Embedding: `BAAI/bge-small-en-v1.5` (33M)
