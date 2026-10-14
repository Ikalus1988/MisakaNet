# PR Genius Anti-Patterns

Common mistakes that cause PR rejection or delays. PR Genius checks for these automatically.

## Critical (Will Block Merge)

### 1. Missing DCO Sign-off
**Pattern:** `git commit` without `-s` flag  
**Fix:** `git commit -s -m "message"` or `git commit --signoff -m "message"`  
**Why:** Developer Certificate of Origin (DCO) is required for all contributions. Without it, the `needs-dco` label blocks merge.

### 2. Stale PR (>14 days without activity)
**Pattern:** PR opened but no commits for 2+ weeks  
**Fix:** Either merge it or add a comment explaining status. Close if abandoned.  
**Why:** Stale PRs clutter the review queue and confuse maintainers.

### 3. CI Failure Ignored
**Pattern:** Red X on checks but no action taken  
**Fix:** Check CI logs, fix the issue, and push a fix commit. Never merge with failing CI.  
**Why:** CI failures indicate real problems (tests, linting, security scans).

### 4. Merge Conflict
**Pattern:** "This branch has conflicts that must be resolved"  
**Fix:** `git fetch upstream && git rebase upstream/main`, resolve conflicts, force push.  
**Why:** Conflicts mean your changes are based on outdated code.

## High Risk (Likely Rejection)

### 5. Large PR (>500 lines)
**Pattern:** PR touches many files or has thousands of lines changed  
**Fix:** Split into smaller, focused PRs. Each PR should do one thing well.  
**Why:** Large PRs are hard to review thoroughly. Reviewers miss bugs.

### 6. Missing Tests
**Pattern:** New feature or bug fix without corresponding tests  
**Fix:** Add tests that cover the changed behavior. Aim for the same coverage as existing code.  
**Why:** Untested code is a liability. Bugs will resurface.

### 7. Secrets in Code
**Pattern:** API keys, passwords, tokens hardcoded in source  
**Fix:** Move to environment variables or config files. Use `.env.example` for documentation.  
**Why:** Secrets in code get scraped by bots within minutes of push.

### 8. Missing Documentation
**Pattern:** New feature without docs updates  
**Fix:** Update README, add inline comments, or create a doc page as appropriate.  
**Why:** Undocumented features are invisible to users.

### 9. Dependency Drift
**Pattern:** Lock file (package-lock.json, poetry.lock) not updated  
**Fix:** Run `npm install` / `poetry lock` and commit the updated lock file.  
**Why:** Inconsistent dependency versions cause "works on my machine" bugs.

### 10. Breaking Change Without Migration
**Pattern:** API or behavior change that breaks existing users  
**Fix:** Add deprecation warnings first, provide migration guide, bump major version.  
**Why:** Breaking changes without warning frustrate users and break trust.

## How PR Genius Checks These

PR Genius runs **automatically on every pull request** — you do not run it locally and there is
no local entry point. `.github/workflows/pr-genius-check.yml` runs the upstream check against your
PR title and body, then `scripts/pr_genius_report.py` renders the enhanced report from
`.pr-genius.yaml` (the rule set, size thresholds and severities) and posts it as a PR comment.

Two things are worth running yourself, and both are in the repository:

**DCO sign-off** — install the hook once and every commit is checked as you make it:

```bash
pip install pre-commit
pre-commit install --hook-type commit-msg
```

**The test suite** — this is the gate that actually blocks:

```bash
pytest tests/          # Python 3.11+; the suite imports tomllib, stdlib only from 3.11
```

The PR Genius check itself is **advisory** (`continue-on-error: true`) — it reports, it never
blocks a merge. Nothing below is a substitute for the two commands above.

Fix issues before submitting to maintain a clean contribution history.
