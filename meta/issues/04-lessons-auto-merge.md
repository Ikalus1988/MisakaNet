# Path-based CI: lessons-only PRs skip full test suite

**Source:** `用户增长-使用者体验改进清单.md` item #5; also `growth-pains.md` pain point #1

## Problem

Every PR runs the full CI pipeline (pytest, coverage, quality gate). For lesson-only PRs (changes under `lessons/` only), this is wasteful — lessons don't affect Python code. The delay discourages lightweight contributions.

## Suggested implementation

In `.github/workflows/pr-checks.yml`, add a scope detection step at the start:

```yaml
- name: Detect Change Scope
  run: |
    SCOPE=$(git diff --name-only HEAD~1 | awk -F/ '{print $1}' | sort -u)
    if echo "$SCOPE" | grep -qv "^lessons$"; then
      echo "scope=full" >> "$GITHUB_OUTPUT"
    else
      echo "scope=lessons-only" >> "$GITHUB_OUTPUT"
    fi
```

- **Full scope** (any change outside `lessons/`): run all gates as today
- **Lessons-only scope**: run only DCO + schema validation, then auto-merge if passing

## Acceptance criteria

- [ ] Lessons-only PRs skip pytest, coverage, quality score gates
- [ ] DCO and schema validation still run on all PRs
- [ ] PR with mixed changes (lessons + code) triggers full pipeline
- [ ] Auto-merge works for passing lessons-only PRs
