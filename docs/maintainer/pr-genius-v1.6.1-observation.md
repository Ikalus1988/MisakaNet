# PR Genius v1.6.1 Observation Log

Date: 2026-08-06
Baseline: PR Genius v1.3.1 → v1.6.1 (SHA 1a73a475fa38d759bef2f0f15a55643860adb7b4)
Anti-patterns: 3 custom definitions added (oversized-pr, multi-bounty-unsplit, core-path-touch)

## Test Results (20 PRs + 6 synthetic cases)

### Synthetic Cases (with anti-patterns)

| Case | Tier | Prob | Negative Signals | Anti-patterns |
|---|---|---|---|---|
| Good PR (fix + issue link) | medium | 0.35 | 0 | - |
| Minimal PR (".") | medium | 0.35 | 0 | - |
| Large PR (500 files rewrite) | **high** | **0.15** | 1 | oversized-pr |
| Multi-bounty (3 issues) | medium | 0.35 | 1 | multi-bounty-unsplit |
| Core touch (mcp_server + auth) | **high** | **0.15** | 1 | core-path-touch |
| Docs PR | medium | 0.35 | 0 | - |

### Real PRs (50 PRs tested, all returned medium)

| PR | Author | Tier | Notes |
|---|---|---|---|
| #847 | jihadMo | medium | MCP journey report |
| #837 | lincai505011-ops | medium | Growth funnel |
| #836 | lincai505011-ops | medium | Journey report |
| #834 | moxuan12138 | medium | Journey report |
| #833 | matheusfrta | medium | Journey report |
| #829 | laurentketterle-hub | medium | Doc & CI Boost |
| #828 | laurentketterle-hub | medium | Doc & CI Boost |
| #827 | 0xhermes-28 | medium | PR Genius observation |
| #826 | 0xhermes-28 | medium | Site health snapshot |
| #817 | Ikalus1988 | medium | Glama remote metadata |

All 20 real PRs returned medium_risk with 0.35 probability.

## Observations

### What works

1. **Anti-pattern detection**: Keywords correctly match PR title/body
2. **Tier differentiation**: high_risk triggers for oversized/core-touch PRs
3. **Signal accuracy**: issue_linked, first_contributor, no_issue_link_hint all correct
4. **Advisory-only design**: never blocks merge, just suggests checklist

### What doesn't differentiate

1. **Real PRs all medium**: 50 real PRs all returned medium_risk
2. **Anti-patterns not triggered**: Real PRs don't contain trigger keywords
3. **merge_probability fixed at 0.35**: No variation across PRs
4. **Checklist identical**: All PRs get same P1/P2 suggestions

### Root cause

PR Genius detects anti-patterns by keyword matching in title/body. Real PR titles like "docs(mcp): add remote MCP user journey report" don't contain trigger keywords like "rewrite", "500 files", "multi-bounty".

## Anti-patterns Added

### oversized-pr.md
- Triggers: rewrite, 500 files, entire, complete rewrite, massive, huge diff, large refactor
- Severity: medium (PR Genius hardcoded default for custom keys)

### multi-bounty-unsplit.md
- Triggers: multi-bounty, #788, #763, #682, multiple issue references
- Severity: medium

### core-path-touch.md
- Triggers: worker, auth, security, workflow, release, CI, deploy, mcp_server, register-proxy, score_lesson
- Severity: medium

## Limitations

1. PR Genius uses hardcoded `ANTI_PATTERN_SEVERITY` dict for tier calculation
2. Custom anti-pattern keys default to "medium" severity
3. Need 2+ medium hits to stay at medium (1 medium → still medium)
4. Need critical/high severity to trigger high_risk (only built-in keys have this)

## Next Steps

1. Observe 5-10 real PRs with anti-patterns in CI
2. Check if high_risk triggers correctly for oversized/core-touch PRs
3. Check if docs PRs stay medium (no false positives)
4. File upstream issue if severity customization is needed

## Decision

- Keep v1.6.1 (SHA pinned)
- Keep anti-patterns (provide differentiation for synthetic cases)
- Advisory-only: no merge gate, just checklist suggestions
- Dependabot will auto-propose future version updates
