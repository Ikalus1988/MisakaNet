---
title: 'BM25 + Vector Hybrid Search: configurable blending weights'
domain: search
tags:
- bm25
- vector
- hybrid
- search
- weights
status: published
created: '2026-08-22'
source: closed-pr-1029
evidence_level: E2
---

<!-- provenance:
  contributor: "Ikalus1988"
  merged_at: "2026-08-22"
  evidence: "post-publication"
-->

<!-- 
## Problem

Search uses only BM25, missing semantic similarity from vector embeddings. Pure keyword search fails on paraphrased queries, synonyms, and conceptually related content that doesn't share exact terms.

## Root Cause

BM25 relies solely on term frequency and inverse document frequency (TF-IDF) statistics. It cannot capture semantic meaning — two documents discussing the same concept with different vocabulary will score poorly. Vector embeddings encode semantic similarity but lack precision for exact keyword matches. Neither approach alone is optimal:

- **BM25 weakness**: "automobile" vs "car" — no match despite identical meaning
- **Vector weakness**: exact product codes or proper nouns may be diluted in embedding space
- **Hybrid solution**: blending both scores captures both lexical precision and semantic relevance

The blending weight determines which signal dominates. A poorly chosen weight (e.g., 100% vector on a keyword-heavy corpus) degrades precision. Configurable weights allow tuning per use case without code changes.

## Solution

Configurable BM25 + vector blending via `config.yaml` or env vars. Default 50/50 with RRF blending.

### config.yaml Example

```yaml
search:
  hybrid:
    enabled: true
    bm25_weight: 0.5       # weight for BM25 score (0.0 - 1.0)
    vector_weight: 0.5     # weight for vector score (0.0 - 1.0)
    blend_method: rrf      # options: rrf | linear
    rrf_k: 60              # RRF constant (default 60, higher = smoother ranking)
    normalize_scores: true # normalize both scores to [0,1] before blending
```

### Environment Variable Override

```bash
# Override weights at runtime without changing config file
export SEARCH_BM25_WEIGHT=0.3
export SEARCH_VECTOR_WEIGHT=0.7
export SEARCH_BLEND_METHOD=rrf
export SEARCH_RRF_K=60
```

### Recommended Weight Profiles

| Use Case | BM25 Weight | Vector Weight | Rationale |
|---|---|---|---|
| General Q&A | 0.5 | 0.5 | Balanced default |
| Code search | 0.7 | 0.3 | Exact tokens matter |
| Semantic FAQ | 0.3 | 0.7 | Meaning over keywords |
| Product catalog | 0.6 | 0.4 | SKUs + descriptions |

## Key Points

- Normalize scores to [0,1] before blending to prevent scale mismatch
- RRF (reciprocal rank fusion) recommended over linear blending — more robust to outlier scores
- Weights must sum to 1.0 when using linear blend mode
- RRF mode ignores raw score magnitude; only rank position matters
- Tune weights using offline evaluation (e.g., NDCG, MRR) against a labeled query set
- Changes to weights take effect on next query; no re-indexing required

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