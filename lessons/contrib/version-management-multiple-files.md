---
{
  "title": "Version Management Across Multiple Files",
  "domain": "devops",
  "tags": ["version", "release", "changelog", "documentation", "metrics", "ssot", "frontend"],
  "status": "published",
  "source": "agent_experience",
  "created": "2026-07-02"
}
---

## Problem

Version number appears in multiple files that need to be updated together:

- `pyproject.toml` — Python package version
- `CHANGELOG.md` — Release notes
- `README.md` — Badge and metrics
- `README.zh-CN.md` — Chinese README
- `docs/index.html` — Frontend version badge
- `docs/integrations/README.md` — Integration docs
- `scripts/mcp_server.py` — MCP server version

Missing any file causes inconsistent version display.

## Root Cause

No single source of truth for version number. Each file hardcodes the version independently, requiring manual synchronization.

The same failure mode applies to public metrics such as lesson counts, node counts, download counts, or leaderboard totals. A partial fix that removes hardcoded numbers can still be wrong if different frontend widgets fetch different data sources:

- hero copy derives from a generated static index
- stats cards derive from a cached API endpoint
- README or join docs keep a manually rounded number
- release notes keep a historical number without labeling it as historical

When those sources drift, users see inconsistent totals even though each individual component is "dynamic".

## Fix

### Checklist for Version Bump

1. **pyproject.toml**
   ```toml
   version = "X.Y.Z"
   ```

2. **CHANGELOG.md**
   ```markdown
   ## vX.Y.Z — YYYY-MM-DD
   
   ### Highlights
   - Feature 1
   - Feature 2
   
   ### Fixes
   - Fix 1
   - Fix 2
   ```

3. **README.md**
   ```markdown
   <a href="..."><img src="https://img.shields.io/badge/lessons-NNN+-blue" /></a>
   ```
   For volatile metrics, prefer rounded claims (`200+`) or generated markers instead of exact hand-edited counts.

4. **README.zh-CN.md**
   - Same updates as README.md

5. **docs/index.html**
   ```html
   <span>vX.Y.Z</span>
   <span>YYYY-MM-DD</span>
   <span id="lesson-count">...</span>  <!-- hydrated from the canonical metric source -->
   ```

6. **docs/integrations/README.md**
   ```markdown
   Search NNN+ lessons directly from your workflow.
   ```

7. **scripts/mcp_server.py**
   ```python
   "version": "X.Y.Z"
   ```

### Checklist for Public Metric SSOT

1. **Choose one canonical source per metric.**
   - Good: `const count = lessons.length` from one loaded index, then fan out to all DOM nodes.
   - Good: CI writes `site-stats.json`, then README/docs/homepage use generated markers.
   - Risky: homepage card uses one API endpoint, search uses one static JSON file, README uses manual text.

2. **Hydrate every visible copy from the same in-memory value.**
   ```js
   const lessons = await loadCanonicalLessons();
   const lessonCount = lessons.length;
   for (const id of ["lesson-count-hero", "lesson-count-card", "lesson-count-search"]) {
     document.getElementById(id).textContent = String(lessonCount);
   }
   ```

3. **Do not keep a second dynamic source just for the same count.**
   If a cached API endpoint and a static JSON index disagree, either make the API the canonical source for all consumers or stop using it for that metric. Treat API branch synchronization as a separate public-contract issue.

4. **Label historical numbers explicitly.**
   Release notes may say "vX.Y.Z snapshot: N lessons", but live product copy should not show snapshot counts beside real-time counters without context.

### Verification

```bash
# Check all version references
grep -rn "old.version" --include="*.md" --include="*.py" --include="*.toml" --include="*.html"

# Verify no stale references remain
grep -rn "OLD_COUNT_A\|OLD_COUNT_B\|OLD_COUNT_C" README*.md docs

# Verify volatile metrics do not have split sources
grep -rn "metric-count\|/api/\|data/.*\\.json" docs README*.md
```

For frontend metric fixes, also inspect the code path: every visible count should be assigned from the same variable or generated artifact. A grep that finds no old number is not enough; a page can still drift when two dynamic loaders return different lengths.

## Notes

- Consider using `bump2version` or similar tool for automated version bumping
- Keep public metrics derived from one source instead of manually syncing many strings
- Update frontend stats by changing the canonical data flow, not by patching each displayed number independently
