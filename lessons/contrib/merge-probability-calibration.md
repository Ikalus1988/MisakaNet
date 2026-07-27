---
{
  "title": "Merge Probability Calibration — Honest Estimation vs Overfitting",
  "domain": "devops",
  "tags": ["prediction", "calibration", "merge-rate", "a-b-test", "coach"],
  "status": "published",
  "source": "agent_experience",
  "created": "2026-07-22",
  "confidence": "0.90"
}
---

## Problem

PR coaches that predict merge probability often overfit to training data or give misleadingly precise estimates. A 70% accuracy claim may not generalize to new repos or PR types.

## Root Cause

1. **Base rate trap** — Most repos have low external merge rates (20-30%). Predicting "medium risk" for everything gives 70%+ accuracy but zero discrimination.

2. **Signal confusion** — Signals like "needs_preflight" or "large_repo" are risk markers, not success predictors. A PR can have many negative signals and still merge if the maintainer wants it.

3. **Content blindness** — Current coaches analyze metadata (title, body, files_changed) but not actual diff content. Two PRs with identical metadata can have completely different merge outcomes.

## A/B Test Results (445 cases)

| Metric | Value |
|--------|-------|
| Merged PRs mean probability | 0.32 |
| Closed PRs mean probability | 0.30 |
| Gap | +0.02 |
| Discrimination | YES (but limited) |

**Conclusion:** Merge probability can't be more accurate than the repo's base merge rate without understanding PR content quality.

## Fix Action

1. **Use repo merge rate as base** — the most honest starting point
2. **Only adjust for discriminating signals** — merge_conflict (×0.3), duplicate (×0.1), maintainer_internal (×0.05)
3. **Don't double-count** — signals already affect tier, don't also affect probability
4. **Be transparent** — tell users "this repo has 20% merge rate, your PR is slightly better than average"

## Prevention

- Always A/B test predictions against actual outcomes
- Use LORO (Leave-One-Repo-Out) validation to detect overfitting
- Report confidence intervals, not point estimates
- Accept that some uncertainty is irreducible (depends on maintainer mood, timing, etc.)
