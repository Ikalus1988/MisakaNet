---
title: "Search SSOT: Fixing Data Source Pollution in Static-Deployed Sites"
domain: devops
tags: [search, ssot, data-source, static-site, worker, github-pages, frontend]
status: published
source: misakanet
created: 2026-07-10
updated: 2026-07-10
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
# Count alignment
python3 -c "import json; print(len(json.load(open('data/lessons.json'))))"
# Expected: 199

curl -s https://misakanet.org/data/lessons.json | python3 -c "import json,sys; print(len(json.load(sys.stdin)))"
# Expected: 199 (same count)

# No pollution
curl -s https://misakanet.org/data/lessons.json | grep -c "CONTEXT COMPACTION"
# Expected: 0
```

## Notes

- `/api/*` routes are intercepted by the Worker — GitHub Pages cannot serve them
- Static JSON is sufficient for search; real-time API is only needed for write operations
- Build workflow should sync data files to `docs/` on each run
- Quality filter should run at search time, not at index time
