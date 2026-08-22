---
{
  "title": "BM25 + Vector Hybrid Search: configurable blending weights",
  "domain": "search",
  "tags": [
    "bm25",
    "vector",
    "hybrid",
    "search",
    "weights"
  ],
  "status": "published",
  "evidence_level": "E2",
  "source": "pr",
  "created": "2026-08-22",
  "author": "unknown",
  "edited_at": "2026-08-22T05:38:33.510130+00:00",
  "merged_by": "unknown"
}
---

## Problem

Search uses only BM25, missing semantic similarity from vector embeddings.

## Solution

Configurable BM25 + vector blending via config.yaml or env vars. Default 50/50 with RRF blending.

## Key Points

- Normalize scores to [0,1] before blending
- RRF (reciprocal rank fusion) recommended
- Weights must sum to 1.0
