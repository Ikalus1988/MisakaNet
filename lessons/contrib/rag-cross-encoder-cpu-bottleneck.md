---
{
  "title": "RAG Cross Encoder CPU Bottleneck",
  "domain": "rag",
  "source": "bootstrap",
  "status": "published",
  "language": "en",
  "tags": [
    "project:self-grow-wiki",
    "severity:medium",
    "node:hermes-wsl"
  ]
}
---


## Problem

RAG knowledge-base answers were too slow (113s cold start, 44s warm query), and the same question produced different answers in different scenarios.

## Root Cause

### Speed Bottleneck

- **The cross-encoder reranker was the only bottleneck**. `BAAI/bge-reranker-v2-m3` (568M parameters) ran pairwise inference for 25 candidates on CPU, taking 25-60s per query.
- All other stages combined (vector retrieval, BM25, exact entity search, LLM generation) took less than 2s.
- Of the 113s cold start, 60s were spent in the reranker; of the 44s warm query, 42.7s were also spent in the reranker.
- The 40s+ "hidden overhead" on the first query was actually the reranker, not ChromaDB. It was located only after adding [TIMING] logs.

### Inconsistent Answers

- `temperature=0.3` still has sampling randomness.
- No `seed` parameter was passed → every LLM call used a different random seed, so the same prompt + same context produced different outputs.
- In group chat scenarios, `share_session_in_channel=true` caused multiple users to share one session, polluting context.

## Solution

### Speed Optimization: Disable the Cross-Encoder Reranker Directly

```python
# RAG Cross-Encoder Reranker CPU bottleneck and LLM determinism tuning
# Option A: change the config variable
_RERANK_TOP_K = 0

# Option B: make _get_reranker() return None directly
def _get_reranker():
    return None
```

**Reason:** Existing RRF fusion (vector + BM25) + exact entity search + topic_tag_boost already provide enough ranking signals. The marginal gain from cross-encoder reranking is very low.

**Result:** Warm query 44s → ~1.2s. Cold start 34s (initial embedding + BM25 load) without affecting subsequent queries.

### Answer Consistency: Tune LLM Parameters

```python
# rag_core.py DEFAULT_TEMPERATURE
DEFAULT_TEMPERATURE = 0       # Change from 0.3 to 0 to remove sampling randomness

# Complete LLM call kwargs
kwargs = dict(
    model=ch["model_id"],
    messages=messages,
    temperature=0,      # Deterministic
    seed=42,            # Fixed seed, reproducible
    top_p=1,            # Disable nucleus sampling
    max_tokens=4096,
    stream=True,
)
```

### Fallback: Isolate Group Chat Sessions

```toml
# cc-connect config or corresponding bot config
[projects.platforms.options]
share_session_in_channel = false  # Independent session per user
```

## Verification

1. Warm query speed: 44s → ~1.2s (tested twice through AP calls)
2. Answer consistency: asking the same query twice in a row produced identical output
3. Ranking quality spot check: answers did not degrade after disabling the reranker


```bash
# Expected result: retrieval logs show the intended chunks and no stale cache or fallback errors.
python3 search_knowledge.py "rag verification smoke test" --lessons
```

Environment: Linux / WSL with Python 3.10 or newer; adapt the query to the affected RAG corpus.

## Lessons Learned

1. **Add [TIMING] logs before optimizing**. Hermes initially guessed the 40s delay was ChromaDB overhead, but logs located it in the reranker. Optimization without data is blind guessing.
2. **Do not run a cross-encoder reranker on CPU**. A 568M-parameter model can take hundreds of milliseconds on GPU, but on CPU it takes half a minute to a minute. If you must use one, switch to `bge-reranker-v2-minicpm-layerwise` (~100M parameters) with GPU inference.
3. **temperature > 0 must be paired with a seed parameter**. Even with temperature=0, some API implementations may still produce tiny differences when no seed is set. The trio temperature=0 + seed=42 + top_p=1 is needed to guarantee determinism.
4. **Shared group-chat sessions are a hidden cause of inconsistent answers**. When debugging "same prompt, different result", check not only model parameters but also the scope of the session key.
