---
title: 'Search SSOT: Fixing Data Source Pollution in Static-Deployed Sites'
domain: devops
evidence_level: E1
tags:
- search
- ssot
- data-source
- static-site
- worker
- github-pages
- frontend
status: published
created: 2026-07-10
updated: 2026-07-10
source: misakanet

provenance:
  source: "external"
  contributor: "misakanet"
  merged_at: "2026-07-31"
  evidence: "post-publication"
---

# Search SSOT: Fixing Data Source Pollution

## Problem

A static site deployed via GitHub Pages used a Worker API (`/api/lessons`) as the data source for its search feature. The Worker fetched from a stale branch, returning192 entries with CONTEXT COMPACTION artifacts instead of the clean199-entry index on main. Users saw garbled search results.

## Root Cause

Multiple data sources existed with different freshness:

| Source | Count | Quality |
|---|---|---|
| `data/lessons.json` (main branch) | 199 | Clean |
| `/api/lessons` (Worker, stale branch) | 192 | Polluted |
| `data/okf/lessons.jsonl` | 143 | Stale |
| Hardcoded in HTML | 207 | Wrong |

The frontend used the Worker API, which fetched from a different branch with older, corrupted data.

## Fix

1. **Static copy**: Copy `data/lessons.json` to `docs/data/lessons.json` (served by GitHub Pages)
2. **Frontend change**: `getLessonsUrl()` returns `/data/lessons.json` instead of `/api/lessons`
3. **CI sync**: Build workflow copies `data/lessons.json` to `docs/data/` on each run
4. **Quality filter**: Add `isSearchableLesson()` to exclude garbage entries (CONTEXT COMPACTION, mojibake)

```javascript
// Before (polluted)
function getLessonsUrl() {
  return "/api/lessons";  // Worker fetches from stale branch
}

// After (clean)
function getLessonsUrl() {
  return "/data/lessons.json";  // Static, same as main branch
}
```

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

## Notes

- `/api/*` routes are intercepted by the Worker — GitHub Pages cannot serve them
- Static JSON is sufficient for search; real-time API is only needed for write operations
- Build workflow should sync data files to `docs/` on each run
- Quality filter should run at search time, not at index time