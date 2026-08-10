# PR Genius Anti-Patterns Guide

Common PR issues detected by PR Genius and how to fix them.

## Overview

PR Genius analyzes PRs for compliance, quality, and maintenance issues. This guide helps contributors avoid common pitfalls.

## Anti-Patterns

### 1. Missing DCO Sign-off

**Detection:** PR Genius flags `DCO_SIGNOFF_MISSING`

**What it means:** Your commits lack the Developer Certificate of Origin sign-off line.

**Fix:**
```bash
# For the last commit
git commit --amend --signoff

# For multiple commits
git rebase --signoff HEAD~3

# Push
git push --force-with-lease
```

**Prevention:** Always use `git commit -s` or add `Signed-off-by: Your Name <email>` to commits.

---

### 2. Stale PR (No Review)

**Detection:** PR Genius flags `STALE_NO_REVIEW`

**What it means:** PR has been open for 14+ days with no maintainer review.

**Fix:**
- Comment on the PR to bump it: "Friendly ping — is there anything I can improve?"
- Check if the maintainer is active (look at recent commits/issues)
- Consider if the PR is still relevant

**Prevention:** Submit PRs to active repos. Check maintainer activity before contributing.

---

### 3. Stale PR (Review Stale)

**Detection:** PR Genius flags `STALE_REVIEW`

**What it means:** Maintainer reviewed, you pushed fixes, but they haven't re-reviewed.

**Fix:**
- Comment: "Changes addressed — ready for re-review"
- Tag the reviewer if possible
- Be patient — maintainers have limited time

**Prevention:** Respond promptly to review comments. Keep PRs small for faster review.

---

### 4. CI Failure

**Detection:** PR Genius flags `CI_FAILURE`

**What it means:** One or more CI checks are failing.

**Fix:**
1. Check the CI logs for the specific failure
2. Common causes:
   - **Linting:** Run `ruff check .` or `black --check .`
   - **Tests:** Run `pytest` locally
   - **Lockfile drift:** Run `pip freeze > requirements.txt` or update lockfile
   - **Type errors:** Run `mypy .` or `pyright .`

**Prevention:** Run linters and tests locally before pushing.

---

### 5. Merge Conflict

**Detection:** PR Genius flags `NEEDS_REBASE`

**What it means:** Your PR has conflicts with the base branch.

**Fix:**
```bash
git fetch upstream
git rebase upstream/main
# Resolve conflicts
git push --force-with-lease
```

**Prevention:** Rebase frequently on upstream/main.

---

### 6. Large PR (>500 lines)

**Detection:** PR Genius flags `LARGE_PR`

**What it means:** PR touches too many files/lines for easy review.

**Fix:**
- Split into smaller, focused PRs
- Each PR should do one thing well
- Use feature flags for incremental rollout

**Prevention:** Write small, focused commits. Submit PRs early and often.

---

### 7. Missing Tests

**Detection:** PR Genius flags `NO_TESTS`

**What it means:** Code changes lack corresponding test coverage.

**Fix:**
- Add unit tests for new functions
- Add integration tests for new features
- Aim for 80%+ coverage on changed code

**Prevention:** Write tests first (TDD) or alongside code.

---

### 8. Hardcoded Secrets

**Detection:** PR Genius flags `SECRET_DETECTED`

**What it means:** PR contains potential API keys, passwords, or tokens.

**Fix:**
```bash
# Remove the secret from history
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch path/to/file' HEAD

# Use environment variables instead
export API_KEY="your-key-here"
```

**Prevention:** Use `.env` files (gitignored), never commit secrets.

---

### 9. Dependency Drift

**Detection:** PR Genius flags `DEPENDENCY_DRIFT`

**What it means:** Lockfile doesn't match dependency declarations.

**Fix:**
```bash
# Python
pip install -e . && pip freeze > requirements.txt

# Node
npm install && package-lock.json updates automatically

# Rust
cargo update && cargo generate-lockfile
```

**Prevention:** Commit lockfiles. Update dependencies regularly.

---

### 10. Documentation Missing

**Detection:** PR Genius flags `NO_DOCS`

**What it means:** New features lack documentation.

**Fix:**
- Update README.md with usage examples
- Add docstrings to new functions
- Update CHANGELOG.md
- Add inline comments for complex logic

**Prevention:** Document as you code, not after.

---

## Priority Levels

| Level | Meaning | Action Required |
|-------|---------|-----------------|
| `critical` | Blocks merge | Fix immediately |
| `high` | Should fix | Fix before review |
| `medium` | Nice to fix | Fix if time permits |
| `low` | Advisory | Consider fixing |

## Getting Help

- Check [CONTRIBUTING.md](../../CONTRIBUTING.md) for repo-specific guidelines
- Ask in PR comments if you're stuck
- Review the [PR Genius observation report](../maintainer/pr-genius-observation.md) for real examples
