---
domain: "ci"
title: "Set fail-fast: false for Matrix Builds to See All Failures"
status: "published"
verification: "metadata-normalized"
{"title": "Set fail-fast: false for Matrix Builds to See All Failures", "domain": "ci", "tags": ["github-actions", "matrix", "workflow-design", "ci-optimization"], "status": "published", "confidence": "0.9", "created": "2026-09-08", "updated": "2026-09-08", "source": "upgraded-docs-framework CI", "verified_date": "2026-09-08", "domain_expert": ""}
---

# Set fail-fast: false for Matrix Builds to See All Failures

## Problem

GitHub Actions matrix builds default to `fail-fast: true`, which cancels all remaining jobs after the first failure. In a 3×5 matrix (3 Python versions × 5 test groups = 15 jobs), this means 13 jobs are cancelled after the first failure, hiding whether other configurations also fail.

This wastes CI compute (you re-run to find all failures) and hides the full scope of breakage.

## Root Cause

The `strategy.matrix` block in GitHub Actions defaults `fail-fast` to `true`:
```yaml
strategy:
  matrix:
    python-version: ["3.10", "3.11", "3.12"]
    test-group: ["unit", "integration", "e2e", "smoke", "regression"]
  # fail-fast: true is implicit — first failure cancels rest
```

This is sensible for fast feedback on single-configuration repos, but wrong for matrix builds where you want to know the full compatibility picture.

## Solution

### Step 1: Add explicit fail-fast: false

```yaml
strategy:
  fail-fast: false
  matrix:
    python-version: ["3.10", "3.11", "3.12"]
    test-group: ["unit", "integration", "e2e", "smoke", "regression"]
```

### Step 2: Verify all matrix jobs run

After pushing, check that all jobs completed (not just the first failure):
```bash
gh run view <RUN_ID> --json jobs --jq '.jobs[] | {name: .name, conclusion: .conclusion}'
```

Expected output should show all 15 jobs with their individual conclusions, not 1 failure + 14 cancelled.

## Verification

Compare the before/after:
- **Before**: 1 failure, 14 cancelled (wasted compute, incomplete data)
- **After**: 15 jobs completed, showing full failure/success matrix

## Notes

- `fail-fast: false` increases CI time when there are failures (all jobs run to completion)
- Use `fail-fast: true` only when you want quick feedback and don't care about the full matrix
- For large matrices (50+ combinations), consider `max-parallel` to limit concurrent jobs:
  ```yaml
  strategy:
    fail-fast: false
    max-parallel: 5
    matrix: ...
  ```