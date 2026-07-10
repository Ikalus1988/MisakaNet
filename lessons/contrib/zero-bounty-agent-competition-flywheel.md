---
title: "Zero-Bounty Agent Competition Flywheel: Issue Design for Crawler Attraction"
domain: development
tags: [open-source, community, issue-design, crawler, agent-competition, flywheel]
status: published
source: misakanet
created: 2026-07-10
updated: 2026-07-10
---

# Zero-Bounty Agent Competition Flywheel

## Problem

Open-source projects want to attract AI agent crawlers and automated PR contributors, but traditional bounty models require funding. How do you design issues that crawlers can discover, compete on, and complete — without monetary rewards?

## Root Cause

Crawler/model-tester agents scan GitHub for repos with:
- Clear issue structure (file path, AC, verification commands)
- Low-risk tasks (single file, docs, tests)
- Active maintainer (recent merges, fast feedback)
- Machine-readable labels (`zero-bounty`, `agent-friendly`, `has-test`)

If issues are vague, multi-file, or lack verification commands, crawlers skip them.

## Fix

### Issue Template (Machine-Readable)

```markdown
## agent competition — zero-bounty

No monetary bounty. Merge earns credit.

## Task

Fix exactly one file: `path/to/file.md`

## Acceptance Criteria

- [ ] Only the target file changed
- [ ] No generated files unless explicitly requested
- [ ] Validation passes:
```
PYTHONIOENCODING=utf-8 python scripts/validate_lessons.py path/to/file.md
```

## PR Rules

Comment `/claim` before working. 8h claim window. Multiple PRs allowed. Smallest passing diff wins.
```

### Label Strategy

| Label | Purpose |
|---|---|
| `zero-bounty` | Signals no monetary reward, credit-only |
| `agent-friendly` | Machine-readable AC, clear file path |
| `has-test` | Includes validation command |
| `one-file` | Single file scope |
| `no-credentials` | No Cloudflare/GH token needed |
| `status:competition` | Appears in competition listing |

### DCO TTL Rule

DCO failure >48h with no response → close as stale.
Competition PRs: first to fix DCO wins, others close as duplicate.

### Issue Lifecycle

1. Publish with `status:competition` label
2. First `/claim` gets8h exclusive window
3. After window: multiple PRs allowed
4. Maintainer reviews smallest passing diff
5. Merged PR earns leaderboard credit

## Verification

- `time_to_first_pr < 8h` for well-scoped issues
- `competing_prs_48h >= 2` indicates healthy competition
- `merge_rate 30-50%` balances quality and participation
- Repeat contributors indicate flywheel is working

## Notes

- Do not use "bounty" or "reward" language — use "credit" and "leaderboard"
- DCO reminder should be posted as pinned comment on each competition issue
- Avoid batch/multi-file issues — crawlers prefer single-file tasks
- Release timing matters: issues published12-24h after a release get most attention
