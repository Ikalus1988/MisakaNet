---
{
  "title": "gh credential helper path mismatch silently breaks git push",
  "domain": "devops",
  "tags": ["git", "github", "credential", "gh", "auth", "push"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "translated_from": "lessons/contrib/git-credential-helper-gh-path-mismatch.md",
  "created": "2026-07-20",
  "updated": "2026-07-20"
}
---

# gh credential helper path mismatch silently breaks git push

> English translation of `lessons/contrib/git-credential-helper-gh-path-mismatch.md`

## Problem

`git push` hangs or errors with:

```text
/home/hp/.local/bin/gh auth git-credential get: 1: /home/hp/.local/bin/gh: not found
```

or:

```text
remote: Repository not found.
fatal: repository 'https://github.com/...' not found
```

even when the repo exists and the token is valid.

## Root Cause

`gh` may live at `/usr/bin/gh` while git’s credential helper points at a **stale path**:

```text
credential.https://github.com.helper=!/home/hp/.local/bin/gh auth git-credential
```

Common after mixed install methods (`apt` vs manual) or moved user local bins.

## Fix

```bash
git config --global --list | grep credential

git config --global --unset-all credential.https://github.com.helper
git config --global --unset-all credential.https://gist.github.com.helper

git config --global credential.helper store
# ensure ~/.git-credentials has a valid token
cat ~/.git-credentials

git ls-remote origin HEAD
```

Or point the helper at the real binary:

```bash
git config --global credential.https://github.com.helper '!$(command -v gh) auth git-credential'
```

## Verification

```bash
git config --global --list | grep helper
git ls-remote origin HEAD   # returns a commit hash
```
