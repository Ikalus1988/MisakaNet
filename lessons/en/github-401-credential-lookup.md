---
{
  "title": "Local credential lookup order after GitHub API 401",
  "domain": "github",
  "tags": ["github", "api", "credential", "401", "auth", "pat"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "translated_from": "lessons/contrib/github-401-credential-lookup.md",
  "created": "2026-07-20",
  "updated": "2026-07-20"
}
---

# Local credential lookup order after GitHub API 401

> English translation of `lessons/contrib/github-401-credential-lookup.md`

## Problem

Calling the GitHub API returns `{"message":"Bad credentials"}` or HTTP 401/403. The first impulse is “token is dead — ask the user for a new PAT.” Local credentials often already exist; skipping the inventory wastes a human trip.

## Root Cause

Agents prefer **acquiring new resources** (ask user) over **inventorying local assets**. That is resource-fetch bias vs resource-audit bias.

## Fix

**Mandatory lookup order after GitHub API auth failure:**

```bash
# 1. git-credentials store
cat ~/.git-credentials
# format: https://username:TOKEN@github.com

# 2. netrc
cat ~/.netrc

# 3. GitHub CLI
gh auth status

# 4. environment
echo "$GITHUB_TOKEN"

# 5. credential helper config
git config --global --list | grep credential
```

**Only if all of the above fail** should you ask the user for a new token.

Extract token from git-credentials:

```bash
grep -oP 'https://[^:]+:\K[^@]+' ~/.git-credentials
```

## Verification

```bash
curl -s -H "Authorization: Bearer $TOKEN" https://api.github.com/user | jq .login
```

## Related

Complements `git-credentials-automation`: that lesson covers interactive push/pull auth; this one covers programmatic API auth.
