# Quality Score v0 — Lesson Quality Algorithm

> Published: 2026-06-19 | Status: v0 (draft, subject to iteration)
> Tracking Issue: [#210](https://github.com/Ikalus1988/MisakaNet/issues/210)

## Purpose

A transparent, deterministic scoring algorithm that measures lesson quality. Used to:

- Surface high-quality lessons in search results
- Flag low-quality lessons for review (`needs-review` label)
- Provide contributors with clear quality targets
- Track quality improvement over time

## The Formula

```python
score = (
    0.5 * root_cause_clarity +
    0.3 * verify_completeness +
    0.2 * domain_coverage
)
```

### Dimension Definitions

#### `root_cause_clarity` (weight: 0.5)

Whether the lesson clearly identifies **why** the problem occurred.

| Criteria | Score |
|----------|-------|
| Root cause is explicitly stated with technical detail (error message, config diff, system state) | 1.0 |
| Root cause is mentioned but lacks technical detail | 0.6 |
| Root cause is missing or vague ("something went wrong") | 0.0 |

#### `verify_completeness` (weight: 0.3)

Whether the lesson provides replicable verification steps.

| Criteria | Score |
|----------|-------|
| Has a `## Verification` section with executable commands and expected output | 1.0 |
| Has verification steps but missing commands or expected output | 0.5 |
| No verification section | 0.0 |

#### `domain_coverage` (weight: 0.2)

Whether the lesson accounts for multiple environments, versions, or edge cases.

| Criteria | Score |
|----------|-------|
| Covers 2+ environments (e.g., WSL + native Linux, or Docker + bare metal) or mentions version-specific behavior | 1.0 |
| Single environment, no version discussion | 0.5 |
| No environment/context information | 0.0 |

## Scoring Thresholds

| Score Range | Label | Action |
|-------------|-------|--------|
| 0.80 - 1.00 | ⭐ high-quality | Promoted in search, merge without review |
| 0.60 - 0.79 | ✅ acceptable | Standard merge, may still need light review |
| 0.40 - 0.59 | ⚠️ needs-review | CI tags automatically, requires maintainer review before merge |
| 0.00 - 0.39 | ❌ draft | Blocked from merge, return to contributor |

## Automatic Scoring (CI)

When CI integration is live (tracking: [#210](https://github.com/Ikalus1988/MisakaNet/issues/210)):

```yaml
# .github/workflows/quality-score.yml (planned)
on: [pull_request]
jobs:
  quality-score:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Score lessons
        run: |
          python3 scripts/score_lessons.py --threshold 0.6
      - name: Tag low-quality
        if: failure()
        run: |
          gh pr edit ${{ github.event.pull_request.number }} --add-label "needs-review"
```

## Manual Scoring (Pre-CI)

Until the CI scorer is implemented, contributors and reviewers can score manually:

```bash
# Check for Verification section
grep -q "^## Verification" lessons/your-lesson.md && echo "verify=1.0" || echo "verify=0.0"

# Check for root cause depth
grep -q "^## Root Cause" lessons/your-lesson.md && echo "clarity=1.0"

# Combined quick check
python3 -c "
import re, sys
text = open(sys.argv[1]).read()
has_root = bool(re.search(r'^## Root Cause', text, re.M))
has_verify = bool(re.search(r'^## Verification', text, re.M))
has_env = bool(re.search(r'platform:|environment:|WSL|Docker|Ubuntu', text, re.I))
clarity = 1.0 if has_root else 0.0
verify = 1.0 if has_verify else 0.0
coverage = 1.0 if has_env else 0.0
score = 0.5*clarity + 0.3*verify + 0.2*coverage
print(f'clarity={clarity} verify={verify} coverage={coverage} score={score:.2f}')
" lessons/your-lesson.md
```

## Future Iterations

| Version | Planned Improvements |
|---------|---------------------|
| v0 (current) | Basic structure scoring, no NLP |
| v1 | Add `reuse_count` weight (how many times searched) |
| v2 | Add `freshness` decay (older lessons score lower) |
| v3 | Integrate community feedback (👍/😕 reactions) |

## References

- [Lesson Checklist](lesson-checklist.md) — Must/Should criteria table
- [TEMPLATE.md](../lessons/TEMPLATE.md) — Lesson structure template
- Issue [#210: Implement Quality Score](https://github.com/Ikalus1988/MisakaNet/issues/210)
