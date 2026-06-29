---
domain: "contrib"
title: "RAG 品牌Filter三坑：条件触发、文件正则、BM25 Cache"
verification: "metadata-normalized"
---
---{"title": "RAG 品牌Filter三坑：条件触发、文件正则、BM25 Cache", "domain": "rag", "tags": ["rag", "brand-filter", "architecture", "chromadb", "bm25", "pitfall"], "confidence": 0.88, "created": "2026-05-29"}---

## Background

During a quality inspection of a FANUC robot RAG knowledge base, the team found three design flaws in the brand-filtering strategy that allowed competitor documents to keep leaking into retrieval results.

## Three Pitfalls

### Pitfall 1: Conditionally Triggered Brand Filtering

**Symptom:** Brand filtering is triggered only when the query contains target-brand keywords (for example, "FANUC").

**Why this is a pitfall:**
- Daily inspection questions usually do not include brand names, such as "What is the difference between the TCP setup method for a welding gun tool and a gripper tool?"
- Front-end users also rarely add brand keywords proactively
- As a result, every inspection bypasses the filter and competitor documents pass through unchecked

**Correct approach:**
- Brand filtering should be always on, and non-target-brand documents should be excluded directly at the retrieval layer
- If all results are excluded, keep the top-k high-scoring results as an emergency fallback, but mark the source warning for the LLM

### Pitfall 2: Filename Regex Instead of Metadata

**Symptom:** Brand filtering uses regex matching on filenames instead of metadata fields.

```python
# RAG brand-filter three pitfalls: conditional trigger, filename regex, BM25 cache
_fanuc_pat = re.compile(r'(?i)fanuc|B-\d{5}|R-30i[AB]|M-\d{3}|A-\d{5}')
filtered = [c for c in chunks if _fanuc_pat.search(c["filename"])]
```

**Why this is a pitfall:**
- Documents whose filenames do not follow brand naming conventions are missed (for example, kap05_1_*.pdf is actually a KUKA document)
- Running regex searches on every query wastes CPU
- Adding a new brand or pattern requires code changes
- Filenames and actual document contents may not match

**Correct approach:**
- Tag the brand during ingestion with a metadata field (`brand: "fanuc" | "kuka" | "abb" | "unknown"`)
- During filtering, read the metadata field directly for an O(1) decision without regex
- Keep brand detection in one full-scan ingestion step instead of scattering it across every query

### Pitfall 3: BM25 Cache and Metadata Drift

**Symptom:** ChromaDB metadata has been updated, but retrieval still returns old data.

**Why this is a pitfall:**
- The RAG system uses a BM25 index to speed up keyword retrieval
- When the BM25 index is built from ChromaDB, it copies metadata into memory and persists it with pickle to `bm25_index.pkl`
- After ChromaDB `update()` changes metadata, the metadata in the BM25 cache is still old
- This makes `meta.get("brand", "unknown")` in `_build_chunk_v2()` always return `"unknown"`

```python
# The meta returned by BM25 search comes from the cache, not live ChromaDB
def search(self, query, n_results, where_filter=None):
    tokens = list(jieba.cut(query))
    scores = self.bm25.get_scores(tokens)
    # scores[i] corresponds to self.metas[i] — stale cached data!
    return [(self.docs[i], self.metas[i], scores[i]) for i in top_indices]
```

**Correct approach:**
- After changing ChromaDB metadata, delete the BM25 cache file and rebuild the index
- Or add a fallback in `_build_chunk_v2()`: if `meta` has no `brand` field, query ChromaDB live
- Cache files are usually large (500MB+) and rebuilds take 2-5 minutes
## Verification

1. Follow the solution steps in order
2. Run any relevant commands or tests to confirm the fix
3. Verify the symptom no longer occurs
4. Check related logs or outputs for expected behavior


## Summary

| Pitfall | Symptom | Fix |
|---|---|---|
| Conditional trigger | Filtering is skipped when the query has no brand name | Always-on filtering |
| Filename regex | Documents with non-standard names are missed | Tag metadata during ingestion |
| BM25 cache | Cache is not refreshed after metadata updates | Explicitly delete and rebuild the cache |

When all three issues exist at the same time, brand filtering is basically ineffective no matter how accurately ChromaDB is tagged.
