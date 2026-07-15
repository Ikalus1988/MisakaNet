---
{
  "domain": "contrib",
  "title": "Cross-Repo Contribution Strategy — Finding and Contributing to New Repos",
  "tags": ["contrib", "strategy", "github", "open-source", "agent"],
  "status": "draft",
  "source": "Multi-repo contribution session",
  "created": "2026-07-15",
  "confidence": "0.90"
}
---

## Problem

Agents and developers often get stuck contributing to the same repos. Finding new repos to contribute to requires systematic exploration.

## Solution

### 1. Use Coach to Evaluate Before Contributing

```bash
# Check if PR would pass review before submitting
python3 skill/pr_genius.py coach "feat: add feature" --repo org/repo --body "Fixes #123"
```

### 2. Look for Repos with These Signals

| Signal | Why |
|--------|-----|
| `good first issue` label | Maintainer wants new contributors |
| `help wanted` label | Active need for contributions |
| Recent merged PRs from external contributors | Proven track record |
| Active maintainer responses | Will get feedback |

### 3. Avoid These Red Flags

| Red Flag | Why |
|----------|-----|
| No `CONTRIBUTING.md` | Maintainer may not want contributions |
| Stale PRs > 30 days | Maintainer may be unresponsive |
| Only maintainer commits | Closed development |

### 4. Harvest Failed PRs for Learning

```bash
# Extract anti-patterns from rejected PRs
python3 scripts/harvest.py org/repo 123 --type anti-pattern
```

### 5. Focus on Your Expertise

Don't try to contribute to repos outside your domain. Focus on:
- Tools you actually use
- Languages you're proficient in
- Problems you've personally encountered

## Verification

1. Run `coach` on planned PR before submitting
2. Check repo's recent merge history
3. Verify no existing PR for same issue

## Related

- `pr-strategy.md` — External PR strategy
- `maintainer-feedback-iteration.md` — Handling review feedback
- `benchmark-honesty-simulated-vs-real.md` — Honest benchmarking
