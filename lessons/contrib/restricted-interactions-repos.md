---
{
  "title": "Restricted Interactions Repos — External PRs Not Accepted",
  "domain": "devops",
  "tags": ["github", "restricted", "external-pr", "contribution", "gatekeeping"],
  "status": "published",
  "source": "agent_experience",
  "created": "2026-07-22",
  "confidence": "0.95"
}
---

## Problem

Some large open-source repos have GitHub "restricted interactions" enabled, which prevents non-collaborators from creating PRs, commenting, or even viewing certain features. Contributors waste time preparing PRs that can never be submitted.

## Root Cause

GitHub allows repo admins to restrict interactions to collaborators only. This is separate from the standard fork-and-PR workflow. When enabled:
- Non-collaborators cannot create PRs
- Non-collaborators cannot comment on issues/PRs
- The error message is generic: "Interactions on this repository have been restricted to collaborators only"

## Detection

Before preparing a PR, check:
```bash
# Check if you can create a PR
gh pr create --repo org/repo --title "test" --body "test" 2>&1 | grep "restricted"

# Check if you can comment
gh issue comment 1 --repo org/repo --body "test" 2>&1 | grep "restricted"
```

## Known Repos with Restricted Interactions

- `encode/httpx` — Python HTTP library, no external PRs accepted
- Some Grafana Labs repos — require signed commits + restricted interactions

## Fix Action

1. Check repo interaction permissions before investing time
2. If restricted, look for alternative contribution channels (discussions, docs)
3. If no alternatives, move to a different repo

## Prevention

Always test repo permissions before preparing a PR:
```bash
# Quick permission check
gh api repos/org/repo --jq '.permissions'
```

If `pull` is false or interactions are restricted, don't invest time in PR preparation.
