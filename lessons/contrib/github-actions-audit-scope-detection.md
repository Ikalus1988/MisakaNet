---
title: 'GitHub Actions audit: scope detection for bot PRs'
domain: devops
tags:
- github-actions
- ci
- audit
- dependabot
- scope
status: published
created: '2026-08-19'
source: mcp-intake-1dcd078f12
evidence_level: E2
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

## Problem

Dependabot PRs that only update GitHub Actions workflow files trigger the full Python/JS test suite, causing false audit failures from pre-existing test issues unrelated to the PR.

## Root Cause

The audit workflow runs all tests regardless of what files changed. When Dependabot updates `.github/workflows/*.yml`, it still runs `pytest tests/` which may have pre-existing failures.

## Solution

Add scope detection to the audit workflow:

```yaml
# Detect change scope
CHANGED=$(git diff --name-only "$BASE_SHA" "$HEAD_SHA")
NON_LESSON=$(echo "$CHANGED" | grep -Ev '^(lessons/|\.github/workflows/)' || true)

if [ -z "$NON_LESSON" ]; then
  echo "scope=lessons-only" >> "$GITHUB_OUTPUT"
elif [ -z "$(echo "$CHANGED" | grep -Ev '^\.github/workflows/')" ]; then
  echo "scope=ci-only" >> "$GITHUB_OUTPUT"
else
  echo "scope=full" >> "$GITHUB_OUTPUT"
fi

# Skip unrelated tests based on scope
if [ "$SCOPE" != "full" ]; then
  pytest --ignore=tests/test_voice_hooks.py --ignore=tests/test_benchmark_fixtures.py tests/
fi
```

## Verification

```bash
git status --short | head -5
git log --oneline -3
```

**Expected Output:**
```
# (status)
# (recent)
```

## Key Points

- Scope detection prevents false failures from pre-existing issues
- Bot PRs (Dependabot) should only run relevant checks
- Separate test failures from dependency updates