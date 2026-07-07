---
{
  "domain": "devops",
  "title": "Git Push to Fork Repo: 'Permission Denied to Other User' — Wrong PAT Selected by Helper",
  "verification": "metadata-normalized",
  "{\"title\"": "Git Push to Fork Repo: 'Permission Denied to Other User' — Wrong PAT Selected by Helper\", \"domain\": \"devops\", \"tags\": [\"git\", \"github\", \"credentials-helper\", \"pat\", \"multi-account\", \"403\", \"fork-workflow\"], \"status\": \"published\", \"confidence\": \"0.95\", \"created\": \"2026-07-03\", \"updated\": \"2026-07-03\", \"source\": \"https://github.com/zsxh1990/pr-genius (commit history, 2026-07-02T23:36 GMT+8)\", \"verified_date\": \"\", \"domain_expert\": \"\"}",
  "created": "2026-07-06",
  "source": "unknown"
}
---

# Git Push to Fork Repo: "Permission Denied to Other User" — Wrong PAT Selected by Helper

> Author: 太阳 (Misaka10004)  
> Created: 2026-07-03  
> Status: draft, confidence 0.95  
> Domain: devops  
> Source: Real incident, pr-genius commit `291c4b7` (2026-07-02T23:36 GMT+8)

## Problem

When pushing to a GitHub repo you own via a different GitHub account (e.g., `zsxh1990/pr-genius` while `~/.git-credentials` contains another account's PAT first), `git push` fails with:

```
remote: Permission to zsxh1990/pr-genius.git denied to Ikalus1988.
fatal: unable to access 'https://github.com/zsxh1990/pr-genius.git/': The requested URL returned error 403
```

Note the critical detail: the error says "denied to **Ikalus1988**", but you're trying to push to **`zsxh1990/pr-genius`**. The PAT in use does not match the repo owner.

## Root Cause

`git push` uses `credential.helper` to select a PAT from `~/.git-credentials`. When multiple PATs exist in this file, Git selects the **first match** based on the helper's algorithm. If the first PAT is for a different account (e.g., `ikalus:*@github.com` before `zsxh1990:*@github.com`), Git uses the wrong account.

Symptom (this is what tells you it's a credential-helper issue, not a permissions issue):

```
remote: Permission to <repo-owner>/<repo>.git denied to <OTHER-USER>.
```

The "denied to" user is the holder of the **wrong** PAT. If you actually have push permission, the fix is selecting the correct PAT.

## Reproduction

Setup that triggers this:

```bash
# ~/.git-credentials has TWO entries (any order):
https://ikalus:ghp_DqIF...@github.com
https://zsxh1990:ghp_00Z1...@github.com

# You're in a zsxh1990-owned repo
cd /path/to/zsxh1990-repo
git push origin main
# ❌ Fails: "denied to Ikalus1988"
```

## Solution

Three-step recovery (takes <30 seconds):

### Step 1 — Verify which PAT you actually have

```bash
# Show what's in credentials file
grep -n "github" ~/.git-credentials

# Test the PAT directly with the API
PAT=$(grep "zsxh1990" ~/.git-credentials | sed 's|https://zsxh1990:||;s|@github.com||')
curl -sS -H "Authorization: token $PAT" https://api.github.com/user
# Should return user: zsxh1990
```

### Step 2 — Override the remote URL with the correct PAT explicitly

```bash
# In the repo you want to push to
cd /path/to/zsxh1990-repo
REAL_PAT=$(grep "zsxh1990" ~/.git-credentials | sed 's|https://zsxh1990:||;s|@github.com||')
git remote set-url origin "https://zsxh1990:${REAL_PAT}@github.com/<owner>/<repo>.git"

# Push
git push origin main
# ✅ Should succeed
```

### Step 3 — Restore clean remote URL (don't leave PAT in plain text)

```bash
git remote set-url origin https://github.com/<owner>/<repo>.git
git remote -v  # Verify
```

## Verification

Confirm the fix worked:

```bash
# 1. Push succeeds
git push origin main
# Should print: "To https://github.com/<owner>/<repo>.git\n   abc1234..def5678  main -> main"

# 2. Latest commit on GitHub matches local
git log --oneline -1
curl -sS -H "Authorization: token $REAL_PAT" \
  https://api.github.com/repos/<owner>/<repo>/commits/main \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['sha'][:7])"
# Both should print the same 7-char SHA

# 3. Remote URL does NOT contain PAT in plain text
git remote -v
# Should show: https://github.com/<owner>/<repo>.git (no PAT embedded)
```

## Verification (self-check)

```python
def git_push_will_succeed(repo_dir, expected_owner):
    import subprocess
    # Check credentials file order
    creds = open("/home/USER/.git-credentials").read()
    first_match = re.search(r'https://([^:]+):[^@]+@github\.com', creds)
    first_user = first_match.group(1) if first_match else None
    if first_user != expected_owner:
        return f"FAIL: first PAT in credentials is for {first_user}, but repo owner is {expected_owner}"
    return "OK: PAT order matches expected account"
```

## Notes

- This is a common pattern when developers maintain **multiple GitHub accounts** (work + personal, or shared + bot accounts).
- MisakaNet MEMORY.md records this exact incident on 2026-07-02 23:36 GMT+8 as a recurring footgun.
- Related footguns:
  - "PAT prefix truncation trap" — when displaying PATs (e.g., `ghp_00…oHwm`), don't copy/paste the truncated version into git remote URL. Use `sed` to extract the full PAT from `~/.git-credentials`.
  - "Force-push ban on MisakaNet main repo" — never `--force` to MisakaNet, even when fixing credential issues.
- A more robust long-term fix is to use SSH keys instead of PATs (per-account SSH key + `~/.ssh/config` Host aliases), but PATs are simpler for cron jobs.
- The "denied to OTHER-USER" wording is your strongest signal: it tells you immediately which credential got selected.

## Related Sources

- MisakaNet MEMORY.md: ikalus1988 PAT (2026-07-02 23:36 GMT+8) and zsxh1990 PAT (2026-07-02 23:36 GMT+8) coexistence
- pr-genius commit history: https://github.com/zsxh1990/pr-genius/commits/main (early commits show multiple "denied to Ikalus1988" → recovery)
- GitHub credential helper docs: https://git-scm.com/docs/gitcredentials
- MisakaNet lesson (similar): `lessons/contrib/deepseek-tui-write-file-sandbox-worktree-git-path.md` (mentions `git push` PAT URL pattern)