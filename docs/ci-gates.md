# CI Gates: Hard vs Advisory

> This document defines which CI checks are **hard gates** (must pass to merge) vs **advisory/external** (informational, won't block merge).

## Hard Gates (must pass)

These checks block merge if they fail. Fix them before requesting review.

| Check | Workflow | What it validates |
|-------|----------|-------------------|
| **DCO / Signed-off-by** | `dco-check.yml` | Every commit has `Signed-off-by:` line |
| **DCO Audit** | `pr-checks.yml` | Same as above, embedded in audit workflow |
| **Secret Scan** | `pr-checks.yml` | No API keys, tokens, or credentials in diff |
| **Dependency Audit** | `pr-checks.yml` | No known vulnerabilities in dependencies |
| **CodeQL (python)** | GitHub default | No security vulnerabilities in Python code |
| **CodeQL (javascript)** | GitHub default | No security vulnerabilities in JS/TS code |

## Soft Gates (advisory, won't block)

These checks provide feedback but won't prevent merge. They may fail due to external issues.

| Check | Workflow | Why it's advisory |
|-------|----------|-------------------|
| **Agent Quality Score** | `pr-checks.yml` | `continue-on-error: true` — score unavailable doesn't block |
| **Run Test Suite** | `pr-checks.yml` | `continue-on-error: true` — tests may fail on external deps |
| **Validate Lesson Schema** | `pr-checks.yml` | `continue-on-error: true` — legacy lessons may not pass |
| **Workers Builds** | Cloudflare bot | External service, frequently fails on bot PRs |
| **submit-pypi** | deploy workflow | Only runs on release tags, not PRs |

## External (not gated)

These are informational only and never block merge.

| Check | Source | Notes |
|-------|--------|-------|
| **Cloudflare Workers** | `cloudflare-workers-and-pages[bot]` | Bot-generated, ignores project needs |
| **Opire bot** | `opirebot[bot]` | Bounty tracking, not code review |
| **CodeRabbit / Devin** | External bots | Review suggestions, not blockers |

## Auto-Merge Gate

The `Auto-Merge Gate` step in `pr-checks.yml` checks `success()` — meaning ALL steps in the audit job must pass. If an advisory step fails (like `continue-on-error: true` steps), the gate still passes because those steps report `success` even on failure.

However, if an **external check** (like Workers Builds) is configured as a required status check in branch protection rules, the Auto-Merge Gate will fail because GitHub sees the external check as failed.

### How to fix

If a good PR is blocked by Auto-Merge Gate due to external checks:

1. **Manual merge**: Maintainer can merge directly (bypass branch protection)
2. **Update branch protection**: Remove external checks from required status checks
3. **Fix the external check**: Address the underlying issue (e.g., remove Cloudflare Workers integration if not needed)

## Adding new checks

When adding a new CI check, decide its gate level:

- **Hard gate**: Use `continue-on-error: false` (default) — blocks merge on failure
- **Soft gate**: Use `continue-on-error: true` — provides feedback but doesn't block
- **External**: Don't add to branch protection required checks
