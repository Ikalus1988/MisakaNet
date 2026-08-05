# Add credibility badges to search results

**Source:** `用户增长-使用者体验改进清单.md` item #2

## Problem

Current search output (`search_knowledge.py`) shows lesson titles but doesn't distinguish core vs contrib, verified vs draft, or how recently the lesson was updated. Users have no way to judge result quality at a glance.

## Suggested implementation

Modify `search_knowledge.py` `_format_output()` to prefix each result with credibility indicators:

```
[core][verified] lesson title
[contrib] community lesson title
[draft] work-in-progress title
```

- `[core]` vs `[contrib]` — origin directory
- `[verified]` if lesson has a `## Verify` section
- Show relative update time (e.g. `updated 3d ago`)

## Acceptance criteria

- [ ] Search output shows domain label for each result
- [ ] Verified status visible without opening the file
- [ ] Output remains readable, not cluttered
- [ ] `--titles` and `--score` modes also updated
