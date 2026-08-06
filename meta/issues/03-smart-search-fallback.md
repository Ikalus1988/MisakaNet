# Smart fallback when search returns no results

**Source:** `用户增长-使用者体验改进清单.md` item #3

## Problem

When `search_knowledge.py` finds no matching results, it shows a generic "Not found" message and suggests adding a new lesson. A user who just tried their first search is likely to leave at this point.

## Suggested implementation

Replace the current no-results output with tiered suggestions:

1. **Domain suggestions** — if the query resembles a known domain tag, suggest narrowing by domain
2. **Broad mode hint** — suggest `--broad` or `--ref` as alternatives
3. **Quick contribution link** — point to the quick lesson template
4. **Existing domain list** — show top domains as examples

Example output:
```
❌ No exact match for 'docker network debug'

Suggestions:
  • Try domain filter: --lessons docker
  • Try broader search: --broad
  • Browse domains: docker / network / python / cloudflare
  • Quick contribution: scripts/quick-lesson.sh
```

## Acceptance criteria

- [ ] No-result output offers actionable next steps
- [ ] Suggestions are computed from actual available domains/lessons
- [ ] Output still fits in terminal, not too verbose
- [ ] Existing `--suggest` mode still works independently
