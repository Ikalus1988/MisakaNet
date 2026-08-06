---
{
  "title": "DCO Auto-Fix Workflow — /fix-dco Command Design & Implementation",
  "domain": "devops",
  "lang": "en",
  "source": "codewhale",
  "status": "published",
  "tags": [
    "github-actions",
    "dco",
    "signoff",
    "issue-comment",
    "auto-fix",
    "fork-pr",
    "plan-b",
    "supply-chain"
  ],
  "created": "2026-06-13 00:00:00 UTC",
  "updated": "2026-06-14 00:00:00 UTC",
  "domain_expert": "codewhale",
  "verified_date": "2026-06-14"
}
---

> Translated from: [lessons/core/dco-auto-fix-workflow.md](../core/dco-auto-fix-workflow.md)

## Root Cause

DCO (Signed-off-by) check failure is one of the most common blockers for contributor PRs. AI Agent-submitted PRs frequently lack sign-off. A one-click auto-fix capability via PR comments is needed.

**Error message** from DCO check:
```
Commit sha: abc1234, Author: user, Committer: user; Expected "Signed-off-by: user <user@example.com>", but got ""
```

**Root cause**: GitHub's DCO check requires every commit to include a `Signed-off-by:` line. When contributors use `git commit` without the `-s` flag, or AI Agents generate commits without sign-off, the DCO check fails. Manual fix requires `git rebase --signoff`, which is a high barrier for new contributors.

## Solution: /fix-dco Command

### Design

A GitHub Actions workflow triggered by issue comments containing `/fix-dco`:

1. Detect `/fix-dco` comment on a PR
2. Check out the PR branch (with fork support via `pull_request_target`)
3. Run `git rebase --signoff` on all commits
4. Force-push the amended branch back to the PR

### Security Considerations

- Only allow `/fix-dco` from PR authors or repo collaborators
- Use a scoped GITHUB_TOKEN with minimal permissions
- Never execute arbitrary code from the PR content
- Validate the comment is exactly `/fix-dco` (no trailing commands)

### Plan B: Supply-chain safe alternative

If force-push to forks is not feasible:
1. Post a comment with exact commands for the contributor to run locally
2. Provide a GitHub Codespaces one-click fix link
3. Use a bot that creates a new PR with signed commits

## Key Gotcha

`pull_request_target` runs in the context of the base repo (has secrets access). Never check out PR code in this trigger without sandboxing. Use `actions/checkout` with `ref: ${{ github.event.pull_request.head.sha }}` and run only git operations, never build/test.
