# Boost core/verified lessons in search ranking

**Source:** `用户增长-使用者体验改进清单.md` item #1

## Problem

Search ranking is driven by BM25 score alone. Core lessons (well-reviewed, stable) and verified lessons (contain `## Verify` section) may rank below contrib or draft content simply because of keyword density.

## Suggested implementation

In `misakanet/search/engine.py`, add post-ranking boost factors:

| Factor | Boost |
|--------|-------|
| Lesson is in `lessons/core/` | +0.15 × BM25 score |
| Has `## Verify` or `## Verification` section | +0.10 × BM25 score |
| Updated within last 30 days | +0.05 × BM25 score |
| Is draft (`status: draft`) | −0.20 × BM25 score |

These multipliers should be configurable at the top of the file (like the existing `WEIGHT_*` constants).

## Acceptance criteria

- [ ] Core lessons rank higher than contrib with equal BM25 scores
- [ ] Verified lessons get a small boost over unverified
- [ ] Draft content still appears but ranked lower
- [ ] Boost weights are defined as module-level constants
- [ ] Existing `--score` mode accounts for boost factors
