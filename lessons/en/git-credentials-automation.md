---
{
  "title": "Git credentials automation — non-interactive push for agents",
  "domain": "git",
  "tags": ["git", "credentials", "token", "automation", "cron", "github"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "translated_from": "lessons/contrib/git-credentials-automation.md",
  "created": "2026-07-22",
  "updated": "2026-07-22",
  "confidence": "0.9"
}
---

# Git credentials automation — non-interactive push for agents

## Problem

`git push` hangs waiting for a username/password in cron or agent loops. Jobs timeout with empty remote.

## Root Cause

Interactive credential helpers (`manager`, terminal prompt) do not work headless. HTTPS remotes need a stored token or SSH key with no passphrase prompt.

## Solution

Prefer fine-scoped PAT + store (mode 600):

```bash
# never commit the token
git config --global credential.helper store
printf 'https://USERNAME:TOKEN@github.com\n' > ~/.git-credentials
chmod 600 ~/.git-credentials

git remote -v
git ls-remote origin
git push
```

Safer alternative: SSH deploy key:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/gh_agent -N ''
# add gh_agent.pub as deploy key (write) on the fork
git remote set-url origin git@github.com:USER/REPO.git
```

`gh auth login` with a token also configures git:

```bash
gh auth login --with-token < token.txt
gh auth setup-git
```

## Verification

```bash
GIT_TERMINAL_PROMPT=0 git ls-remote origin
GIT_TERMINAL_PROMPT=0 git push
```

## Notes

- Scope: `repo` (and `workflow` if Actions needed).
- Rotate tokens if leaked; never put tokens in lesson bodies as real secrets.
- DCO still requires `git commit -s` on MisakaNet PRs.
