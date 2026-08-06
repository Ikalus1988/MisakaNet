# Crawler A/B Experiment — 2026-07-14

## Hypothesis

v2.8.0 had crawler PRs because issues had `bounty` label and standard bounty formatting. v2.9.0+ lost crawlers when labels changed to `zero-bounty` / `status:competition`.

## Experiment Design

**Start:** 2026-07-14
**End:** 2026-07-21 (7 days)
**Metric:** External PRs, issue comments, claims

### Experimental Group (6 issues)

Enhanced with: `bounty` label + `[Bounty][$0]` title prefix + reward text in body

| Issue | Title | Type |
|-------|-------|------|
| #429 | [Bounty][$0][agent competition] Blind test homepage SAG-Lite search | Test |
| #459 | [Bounty][$0][Benchmark] Run LessonReuseBench | Benchmark |
| #290 | [Bounty][$0][Docs] 5-minute quickstart | Docs |
| #302 | [Bounty][$0][Search] Show match reason | Search |
| #304 | [Bounty][$0][Search] --json output | Search |
| #257 | [Bounty][$0] Translate Chinese lessons | Content |

### Control Group (remaining issues)

Standard labels: `status:competition`, `agent-friendly`, no `bounty` label

| Issue | Title | Type |
|-------|-------|------|
| #352 | Decide verified/ semantics | Protocol |
| #354 | Add trust_tiers | Protocol |
| #318 | Cursor integration | Ecosystem |
| #317 | VS Code extension | Ecosystem |
| #313 | Query expansion | Search |
| #314 | Typo tolerance | Search |
| ... | (others) | Various |

## Baseline (pre-experiment)

| Metric | Experimental | Control |
|--------|-------------|---------|
| External PRs | 0 | 0 |
| Issue comments | 0 | 0 |
| Claims | 0 | 0 |

## Day 1 (2026-07-14)

- Added `bounty` label to all 22 competition issues
- Updated 6 experimental issues with `[Bounty][$0]` title + reward text
- Waiting for crawler discovery

## Day 7 (2026-07-21)

(TODO: fill in results)

| Metric | Experimental | Control |
|--------|-------------|---------|
| External PRs | | |
| Issue comments | | |
| Claims | | |
| Unique contributors | | |

## Conclusion

(TODO: fill in after 7 days)
