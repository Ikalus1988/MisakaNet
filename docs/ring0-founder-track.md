# Ring-0: Founder Track + Ring Load Redefinition

> Status: Proposal | 2026-06-19
> Motivation: Ring-1 competition overload — core architecture tasks marked as Ring-2 but attract Ring-1-level competition

## Problem

Current Ring system:

| Ring | Description | Score |
|------|-------------|-------|
| Ring-1 | High-value tasks, open to all | 2-5 |
| Ring-2 | Medium-value tasks | 1-2 |
| Ring-3 | Maintenance tasks | 0.5-1 |

Issues identified in the Q2 review:
1. **Ring-1 competition overload** — Core architecture tasks (e.g., OpenClaw integration) marked Ring-2 to reduce pressure, but still attracted Ring-1-level attention
2. **No founder protection** — Critical architectural decisions shouldn't be raced on by newcomers
3. **Claim window mismatch** — Global 8h window (increased from 4h in Jun 2026) is a one-size-fits-all. Ring-4 newcomers need more time; Ring-1 experts need less. Ring-specific windows would be fairer across timezones.
4. **No progress checkpoint** — Claims without progress stall the queue

## Proposed Changes

### Add Ring-0 (Founder Track)

| Ring | Description | Access | Score | Claim Window |
|------|-------------|--------|-------|-------------|
| Ring-0 | **Founder-only tasks**: architecture decisions, security reviews, core design | Ikalus1988 only | 5-10 | N/A (direct assign) |
| Ring-1 | **High-value tasks**: new features, major refactors, cross-cutting changes | All contributors | 2-5 | 6h |
| Ring-2 | **Medium tasks**: specific features, quality improvements | All contributors | 1-2 | 6h |
| Ring-3 | **Maintenance**: bug fixes, CI tweaks, documentation | All contributors | 0.5-1 | 12h |
| Ring-4 | **Newcomer**: translations, verify steps, tags, filenames | First-time contributors | 0.3-0.5 | 28h (exclusive) |

### Ring-0 Task Types

Tasks that should be Ring-0 (directly assigned, no claim):

- Security vulnerability fixes
- Core architecture changes (SKP protocol, lesson schema)
- Critical dependency decisions
- Repository ownership/access changes
- Release management
- License changes

### Claim Window Adjustment

| Current | Proposed | Rationale |
|---------|----------|-----------|
| 8h for all rings | 6h for Ring-1/2, 12h for Ring-3, 28h for Ring-4 | Fairer across global timezones, lower-stakes tasks get longer windows |

### Progress Checkpoint

Add a mid-claim checkpoint:

```text
Claim → [2h] Draft PR required → [4h] PR ready for review
                              → No draft → auto-release lock
```

```yaml
# .github/workflows/claim-enforcer.yml (proposed change)
checkpoint_timeout: 2h  # from claim to Draft PR
auto_release: true       # release lock if no progress
notify_channel: issue    # ping on release
```

## Implementation Plan

1. Update `docs/plans/ring-system.md` with new definitions
2. Add Ring-0 label to GitHub (label: `ring:0`)
3. Update claim-enforcer.yml with checkpoint logic
4. Add timezone hint in claim UI: "Window closes at <local-time> for your timezone"

## References

- [Ring-4 Newcomer Track](ring4-newcomer-track.md)
- [Example Feature Plan](plans/example-feature.md)
