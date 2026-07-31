---
{
  "title": "gh credential helper path error causes silent git push failures",
  "domain": "devops",
  "tags": ["git", "github", "credential", "gh", "auth", "push"],
  "status": "published",
  "lang": "en",
  "source": "wasim-builds",
  "translated_from": "lessons/contrib/git-credential-helper-gh-path-mismatch.md",
  "created": "2026-07-31",
  "updated": "2026-07-31"
}
---

# gh credential helper path error causes silent git push failures

> English translation of `lessons/contrib/git-credential-helper-gh-path-mismatch.md`

## Problem

Running `git push` hangs or fails with:

```
/home/hp/.local/bin/gh auth git-credential get: 1: /home/hp/.local/bin/gh: not found
```

Or:

```
remote: Repository not found.
fatal: repository 'https://github.com/...' not found
```

But the repo exists and the token is valid.

## Root Cause

`gh` is installed at `/usr/bin/gh`, but the git global credential helper config points to a non-existent path:

```
credential.https://github.com.helper=!/home/hp/.local/bin/gh auth git-credential
                                                    ^^^^^^^^^^^^^^^^^^
                                                    this path does not have gh binary
```

This is usually a leftover from automatic credential helper configuration after installing `gh`. On WSL Ubuntu, `apt install gh` puts `gh` at `/usr/bin/gh`, but the credential helper may point elsewhere.

## Fix

### 1. Check current credential helper config

```bash
git config --global --list | grep credential
```

### 2. Remove the broken gh credential helper

```bash
git config --global --unset-all credential.https://github.com.helper
git config --global --unset-all credential.https://gist.github.com.helper
```

### 3. Ensure the correct credential store is kept

```bash
git config --global credential.helper store
# confirm .git-credentials has a valid token
cat ~/.git-credentials
# format: https://username:TOKEN@github.com
```

### 4. Verify

```bash
git ls-remote origin HEAD
# should return commit hash without errors
```

## Verification

After the fix, confirm the credential chain is clean:

```bash
git config --global --list | grep helper
# expected: credential.helper=store
# should NOT show gh auth git-credential

# test push
git push
# should push successfully without hanging or errors
```

## Prevention

- After installing `gh` and running `gh auth login`, check whether the credential helper introduced a wrong path
- If using both `credential.helper store` and `gh auth git-credential`, ensure the `gh auth git-credential` path matches the actual binary location
- Use `which gh` to confirm the real path, then compare it with the credential helper path in git config

## Related

- `git-credential-helper-gh-path-mismatch` (Chinese original)
