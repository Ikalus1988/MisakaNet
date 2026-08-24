# Worker BM25 Search

This document describes the pre-computed BM25 search index for the MisakaNet Worker.

## Overview

The Worker search was previously using naive keyword matching:

```javascript
if (text.includes(q)) score += 10;      // exact phrase
for (const w of qWords) {
  if (text.includes(w)) score += 2;     // word match
  if (title.includes(w)) score += 1;    // title boost
}
```

Now it uses proper BM25 scoring with:
- **IDF weighting**: Rare terms score higher than common terms
- **Document length normalization**: Short documents aren't penalized
- **Pre-computed inverted index**: O(1) term lookups instead of O(n) full scans

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Build Index    │────▶│  Sync to KV      │────▶│  Worker Search  │
│  (Python)       │     │  (POST endpoint) │     │  (BM25 scoring) │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

### 1. Build Index

```bash
python scripts/build_worker_index.py \
  --lessons lessons/ \
  --output data/worker-index.json \
  --optimize \
  --stats
```

Output:
```
Loaded 435 lessons
Building BM25 index...
Index written to data/worker-index.json (250,379 bytes)

Index Statistics:
  Documents: 435
  Unique terms: 1,710
  Avg doc length: 10.5 tokens
  BM25 parameters: k1=1.5, b=0.75
```

### 2. Sync to KV

```bash
export SYNC_TOKEN="your-sync-token"
python scripts/sync_index_to_kv.py --index data/worker-index.json
```

Or via CI:
```yaml
- name: Build and sync search index
  run: |
    python scripts/build_worker_index.py --lessons lessons/ --output data/worker-index.json --optimize
    python scripts/sync_index_to_kv.py --index data/worker-index.json
  env:
    SYNC_TOKEN: ${{ secrets.SYNC_TOKEN }}
    WORKER_URL: https://misakanet.dev
```

### 3. Worker Search

The Worker automatically uses the BM25 index when available:

```javascript
// In handleMcpRequest (misakanet_search tool)
const bm25Index = await loadBM25Index(env);
if (bm25Index) {
  results = searchLessonsBM25(bm25Index, query, domain, top);
  source = "worker-bm25";
} else {
  results = searchLessons(lessons, query, domain, top);
  source = "worker-search";  // fallback
}
```

## BM25 Algorithm

BM25 (Best Matching 25) is a ranking function used by search engines:

```
score(D, Q) = Σ IDF(qi) · (f(qi, D) · (k1 + 1)) / (f(qi, D) + k1 · (1 - b + b · |D|/avgdl))
```

Where:
- `IDF(qi)`: Inverse Document Frequency of term qi
- `f(qi, D)`: Term frequency of qi in document D
- `|D|`: Length of document D
- `avgdl`: Average document length
- `k1 = 1.5`: Term frequency saturation parameter
- `b = 0.75`: Length normalization parameter

### IDF Calculation

```python
idf = log((N - df + 0.5) / (df + 0.5) + 1)
```

Where:
- `N`: Total number of documents
- `df`: Number of documents containing the term

## Index Format

```json
{
  "version": 1,
  "built_at": "2026-08-24T02:30:00Z",
  "docCount": 435,
  "avgDocLen": 10.5,
  "k1": 1.5,
  "b": 0.75,
  "terms": {
    "docker": {
      "df": 45,
      "idf": 2.1234,
      "docs": [
        {"doc": 0, "tf": 3, "len": 15},
        {"doc": 5, "tf": 1, "len": 8}
      ]
    }
  },
  "docs": [
    {
      "id": "docker-build-fails",
      "title": "Docker Build Fails with Permission Denied",
      "domain": "devops",
      "path": "lessons/contrib/docker-build-fails.md",
      "len": 15
    }
  ]
}
```

## API Endpoints

### POST /api/search-index

Sync index to KV (requires SYNC_TOKEN).

```bash
curl -X POST https://misakanet.dev/api/search-index \
  -H "Content-Type: application/json" \
  -H "X-Sync-Token: $SYNC_TOKEN" \
  -d @data/worker-index.json
```

Response:
```json
{
  "success": true,
  "docCount": 435,
  "termCount": 1710
}
```

### GET /api/search-index

Get current index statistics.

```bash
curl https://misakanet.dev/api/search-index
```

Response:
```json
{
  "available": true,
  "docCount": 435,
  "termCount": 1710,
  "avgDocLen": 10.5,
  "builtAt": "2026-08-24T02:30:00Z"
}
```

## Optimization

The `--optimize` flag removes low-frequency terms to reduce index size:
- Removes terms with `df = 1` (appear in only one document)
- Keeps long unique terms (likely specific technical terms)

Typical size reduction: 30-40%

## Monitoring

The Worker logs which search method was used:

```javascript
debugLog(env, 2, "BM25 search", { query, results: results.length });
debugLog(env, 2, "Fallback search", { query, results: results.length });
```

Check the `source` field in search responses:
- `"worker-bm25"`: Using pre-computed index
- `"worker-search"`: Using naive fallback

## Related Issues

- Implements #1189
