{"title": "Search Quota Exhaustion Causes False Zero Results", "domain": "devops", "source": "MisakaNet local search testing", "status": "draft", "tags": ["search", "quota", "rate-limit", "misleading-error", "debugging"], "created": "2026-07-10 00:00:00 UTC", "updated": "2026-07-10 00:00:00 UTC", "confidence": "0.95", "verified_date": "2026-07-10"}

## Verification

1. Run `python3 search_knowledge.py "test query"` 5 times
2. Run a 6th query — should see "搜索额度已用尽" message
3. Verify that queries that previously returned results now return 0 results
4. Delete `misakanet/.quota.json` and retry — results should reappear

## Search Quota Exhaustion Causes False Zero Results

### Problem

When running multiple search queries in quick succession, the local MisakaNet search returns 0 results for queries that should have matches. This is misleading because it appears the knowledge base has no relevant content, when in fact the search quota has been exhausted.

**Symptoms:**
- First 5 queries return results normally
- Subsequent queries return 0 results with no error message
- The "零结果" appears to be a content gap, but is actually a rate limit

**Root Cause:**

MisakaNet's local search has a 5-query-per-session quota (stored in `misakanet/.quota.json`). When exhausted, the search silently returns 0 results instead of showing the quota error message.

**Impact:**
- False negative: Appears content doesn't exist when it does
- Misleading debugging: Users think the knowledge base is incomplete
- Wasted time: Users may create duplicate lessons for content that already exists

### Solution

**Immediate fix:**
```bash
# Reset the quota
rm misakanet/.quota.json

# Or contribute a lesson to restore quota
python3 scripts/queue_lesson.py -t "title" -d domain "content"
```

**Prevention:**
- Check quota before running multiple queries: `cat misakanet/.quota.json`
- Run searches with sufficient gaps between them
- For bulk testing, reset quota between test batches

**Code fix suggestion:**
The search should return the quota error message instead of silently returning 0 results. This would prevent the false-zero confusion.

### Verification

```bash
# 1. Reset quota
rm misakanet/.quota.json

# 2. Run 5 queries
for i in {1..5}; do python3 search_knowledge.py "test"; done

# 3. Run 6th query — should show quota message
python3 search_knowledge.py "test"
# Expected: "搜索额度已用尽 (5/5)" message, NOT silent 0 results

# 4. Verify quota file
cat misakanet/.quota.json
# Expected: {"search_count": 5, "quota_max": 5}
```

### Related

- Issue #429: SAG-Lite search QA field report
- PR #442: Field report with false zero-result findings
- `misakanet/profile.py`: Quota management code
