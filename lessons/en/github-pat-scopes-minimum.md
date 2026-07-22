---
{
  "title": "Minimum GitHub PAT scopes for agent PR work",
  "domain": "github",
  "tags": ["github", "pat", "scopes", "security", "pr", "agent"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "created": "2026-07-22",
  "updated": "2026-07-22",
  "confidence": "0.9"
}
---

# Minimum GitHub PAT scopes for agent PR work

## Problem

Agent cannot push to a fork or open PRs; or a PAT is over-scoped (`admin:org`) and risky if leaked.

## Root Cause

Classic PAT created with no scopes, or with kitchen-sink scopes. Fine-grained tokens missing Contents/PRs write on the fork.

## Solution

For fork + PR on public repos, classic PAT minimum:

- `repo` (public_repo alone is not enough for private forks)
- `read:org` if org SSO
- `workflow` only if editing Actions workflows

```bash
# store mode 600
printf '%s\n' "$PAT" > ~/hermes-moneymaker/secrets/github-pat.txt
chmod 600 ~/hermes-moneymaker/secrets/github-pat.txt
gh auth login --with-token < ~/hermes-moneymaker/secrets/github-pat.txt
gh auth status
gh api user -q .login
```

Google-SSO accounts use **email OTP** for sudo mode, not password.

## Verification

```bash
gh auth status
git ls-remote git@github.com:USER/FORK.git || git ls-remote https://github.com/USER/FORK.git
```

## Notes

- Rotate on leak suspicion.
- Prefer deploy keys for single-repo write bots.
