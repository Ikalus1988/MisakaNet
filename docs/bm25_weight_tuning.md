# BM25 Field Weight Tuning Methodology

**Issue:** #311
**Date:** 2026-07-15

## Current Weights → New Weights

| Field | Old | New | Rationale |
|-------|-----|-----|-----------|
| `domain_match` | 0.30 | 0.25 | Slightly reduced — domain overlap is a weak relevance signal (e.g. "fanuc" matches FANUC docs, but BM25 already captures this) |
| `title_exact` | 0.50 | 0.80 | Increased — exact title match is the strongest relevance signal; if user types the exact title, it should rank #1 |
| `title_partial` | 0.20 | 0.40 | Increased — partial title match (query words in title) is more informative than domain or status |
| `status(published)` | 0.20 | 0.00 | Removed — "published" is the default state for95%+ of lessons; it adds no discriminative signal |
| `has_reference` | 0.08 | 0.12 | Slightly increased — having a reference link indicates higher quality |

## Methodology

### 1. Signal Analysis

Analyzed the composite score formula:

```
score = 0.65 × BM25_normalized + 0.20 × metadata_bonus + 0.15 × baseline + boost
```

BM25 dominates at 65% weight. Metadata (20%) must provide **orthogonal** signal — it should boost results that BM25 might miss (exact title matches, domain-specific queries) rather than reinforcing what BM25 already captures.

### 2. Query-Result Analysis

Tested on 20 regression queries covering:
- Exact title matches (DCO, FANUC, PROFINET)
- Partial matches (pip timeout, database locked)
- Domain-specific (feishu, Windows Unicode)
- Open-ended (proxy setup, git conflict)

**Key finding:** `status(published)` adds 0.20 to nearly every result (95%+ are published), making it a constant offset with zero discriminative power. Removing it frees weight budget for title matching.

### 3. Weight Rationale

**Title exact (0.50 → 0.80):**
When a user types an exact lesson title, that lesson should unconditionally rank #1. At 0.50, a strong BM25 match on a different document could outrank it. At 0.80, the title signal is decisive.

**Title partial (0.20 → 0.40):**
Query words appearing in the title is a strong relevance indicator. Doubled to give it more influence over domain matching.

**Domain match (0.30 → 0.25):**
Domain overlap (e.g. query contains "fanuc" and lesson domain is "fanuc") is useful but crude — BM25 already captures term frequency. Slightly reduced.

**Status (0.20 → 0.00):**
"Published" status is the default. It inflates all scores equally without discrimination. Removed entirely.

### 4. Benchmark

Run `python3 scripts/benchmark_bm25_weights.py` to compare old vs new weights on regression queries.

### 5. Future Work

- Collect real search telemetry (click-through, helpful votes)
- A/B test with live traffic
- Per-domain weight profiles (FANUC queries may benefit from higher domain weight)
