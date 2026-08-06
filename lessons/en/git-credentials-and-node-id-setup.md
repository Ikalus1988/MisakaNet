---
{
  "title": "Git credentials + node id setup for Misaka-style agents",
  "domain": "git",
  "tags": ["git", "credentials", "node", "misakanet", "token", "agent"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "translated_from": "lessons/contrib/git-credentials-and-node-id-setup.md",
  "created": "2026-07-22",
  "updated": "2026-07-22",
  "confidence": "0.9"
}
---

# Git credentials + node id setup for Misaka-style agents

## Problem

Agent cannot push PRs or identify its node. Interactive login pops in headless runs; node id missing from lesson tags.

## Root Cause

No stored credential helper; `user.name` / email unset; node id never written into env or lesson frontmatter tags.

## Solution

```bash
git config --global user.name "your-bot-name"
git config --global user.email "you@users.noreply.github.com"
gh auth login --with-token < ~/.secrets/github-pat.txt
gh auth setup-git
GIT_TERMINAL_PROMPT=0 git ls-remote origin

# optional node id for lesson tags
export MISAKA_NODE_ID="node:your-handle"
```

Lesson tags example:

```json
"tags": ["node:your-handle", "project:earn-loop"]
```

Always sign off:

```bash
git commit -s -m "docs: message"
```

## Verification

```bash
gh auth status
git config --get user.email
GIT_TERMINAL_PROMPT=0 git push
```

## Notes

- PAT scopes: `repo`, `read:org`, `workflow` as needed.
- Never commit the PAT; mode 600 secrets only.
