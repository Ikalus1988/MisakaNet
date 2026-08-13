# Implementation Plan: Pre-commit Hooks

## Step 1: Setup pre-commit environment
1. Install pre-commit package:
   ```bash
   pip install pre-commit
   ```

## Step 2: Configure hooks
1. Create `.pre-commit-config.yaml` with:
   - Ruff hooks (lint + format)
   - DCO verification
   - Lesson lint with severity filter

## Step 3: Implement lesson-lint
1. Create `scripts/lesson_lint.py` with:
   - Markdown validation rules
   - Severity-based filtering
   - Integration with pre-commit framework

## Step 4: Add setup script
1. Create `scripts/setup-dev.sh` to:
   - Install pre-commit
   - Install project dependencies
   - Register hooks

## Step 5: Test locally
1. Verify hooks trigger on:
   - Git commit
   - File changes
   - New lesson additions

## Step 6: CI integration
1. Keep existing CI checks as backup
2. Add pre-commit to CI for verification