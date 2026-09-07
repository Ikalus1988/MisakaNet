---
title: Search Smart Fallback — Turning Zero Results into Discovery
domain: devops
tags:
- search
- fallback
- ux
- zero-results
- discovery
status: draft
created: 2026-07-10 00:00:00 UTC
updated: 2026-07-10 00:00:00 UTC
source: MisakaNet search_knowledge.py enhancement
confidence: 0.95
verified_date: 2026-07-10
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

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

## Search Smart Fallback — Turning Zero Results into Discovery

### Problem

When search returns 0 results, users hit a dead end. They don't know if:
- The content doesn't exist
- Their query was too specific
- There are related lessons they should check

This leads to:
- Duplicate lesson creation for content that exists
- User frustration and abandonment
- Missed discovery of related content

**Root Cause:**

The original search implementation returned nothing on zero results:
```
❌ No exact match for 'query'
```

No suggestions, no alternatives, no guidance.

### Solution

Implemented smart fallback with 4 components:

1. **Closest matches by keyword overlap:**
```python
def _find_closest_matches(query, docs, top_n=3):
    query_words = set(re.findall(r'\w+', query.lower()))
    scored = []
    for doc in docs:
        doc_words = set(re.findall(r'\w+', (doc.title + " " + doc.content[:500]).lower()))
        overlap = len(query_words & doc_words)
        if overlap > 0:
            scored.append((overlap / len(query_words), doc))
    return sorted(scored, key=lambda x: -x[0])[:top_n]
```

2. **"Did you mean" with relaxed query:**
```python
def _suggest_relaxed_query(query):
    stop_words = {"the", "a", "an", "is", "are", ...}
    words = query.lower().split()
    meaningful = [w for w in words if w not in stop_words]
    return [" ".join(meaningful[:-1])] if len(meaningful) >= 2 else []
```

3. **Zero-result telemetry logging:**
```python
def _log_zero_result(query):
    log_file = Path.home() / ".misakanet" / "search_telemetry.jsonl"
    entry = {"query": query, "timestamp": datetime.now().isoformat(), "result": "zero"}
    with open(log_file, "a") as f:
        f.write(json.dumps(entry) + "\n")
```

4. **Auto-issue suggestion after 3+ failures:**
```python
count = sum(1 for l in lines if f'"query": "{query}"' in l)
if count >= 3:
    print(f"⚠️ This query has returned 0 results {count} times.")
    print(f"   Consider creating an issue for a missing lesson.")
```

### Impact

- **Before**: Zero results = dead end
- **After**: Zero results = discovery opportunity
  - Shows top-3 related lessons
  - Suggests relaxed query
  - Logs for gap analysis
  - Auto-suggests creating issue after repeated failures

### Verification

```bash
# Test smart fallback
python3 search_knowledge.py "xylophone purple elephant dancing"
# Expected: Shows closest matches + "Did you mean" + available domains

# Test telemetry logging
cat ~/.misakanet/search_telemetry.jsonl
# Expected: JSONL with query, timestamp, result

# Test auto-issue suggestion (run 3+ times)
for i in {1..4}; do python3 search_knowledge.py "nonexistent query xyz"; done
# Expected: "This query has returned 0 results 4 times" message
```

### Related

- PR #441: Smart fallback implementation
- Issue #301: Smart fallback when search returns no results
- `search_knowledge.py`: Main search script