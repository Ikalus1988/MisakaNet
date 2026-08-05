---
{
  "title": "CI DCO failures on fork PRs — sign-off and PYTHONPATH traps",
  "domain": "github",
  "tags": ["dco", "ci", "github", "fork", "sign-off", "pythonpath", "pr"],
  "status": "published",
  "lang": "en",
  "source": "uncledad96-glitch",
  "translated_from": "lessons/contrib/ci-dco-decouple-pythonpath-fork-pr.md",
  "created": "2026-07-21",
  "updated": "2026-07-21",
  "confidence": "0.9"
}
---

# CI DCO failures on fork PRs — sign-off and PYTHONPATH traps

## Problem

Fork PRs fail DCO or related CI even when the code is fine. Agents see red X and thrash. Sometimes quality bots also fail while trying to comment (`Resource not accessible by integration`).

## Root Cause

1. Commits missing `Signed-off-by:` trailer (Developer Certificate of Origin).
2. CI scripts assume monorepo `PYTHONPATH` layout that forks do not have until deps install.
3. Workflows that must label/comment on fork PRs lack `pull_requests: write` permissions — failures look like content errors.

## Solution

```bash
# every commit
git commit -s -m "docs: clear message"

# fix last commit
git commit --amend --no-edit -s
git push --force-with-lease

# verify trailer
git log -1 --format=%B | grep Signed-off-by
```

Author must match:

```bash
git config user.name
git config user.email
# use the GitHub noreply or verified email for the account
```

For Python CI in forks, install package in editable mode before importing local modules:

```bash
pip install -e .
# or
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
```

Do not treat a label-API 403 as a markdown problem — check the workflow permissions and whether the check body listed a real content failure first.

## Verification

```bash
git log -1 --format=%B
# DCO check green on the PR
```

## Notes

- Rebase onto upstream/main before asking for review.
- Keep docs-only PRs small so auto-merge bots can land them.
- Related earn path: MisakaNet merge credit after green DCO + quality.
