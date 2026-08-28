---
{
  "title": "DCO Signoff Lost During Force Push",
  "domain": "devops",
  "tags": ["git", "dco", "signoff", "force-push", "pull-request"],
  "status": "published",
  "evidence_level": "E0",
  "source": "session-feedback",
  "created": "2026-08-04",
  "updated": "2026-08-04",
  "metadata": {
    "type": "feedback",
    "originSessionId": "c8d99950-7aef-46ad-b4ce-4d0f910c86e9",
    "modified": "2026-08-04T10:19:47.621Z"
  }
}
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

## Problem

Force push 后 DCO (Developer Certificate of Origin) check 持续失败，即使本地 commit 有 `Signed-off-by`。

## Root Cause

1. `git commit --amend --signoff` 只修改当前 commit，但 PR 可能包含多个 commit
2. `git reset --soft main` 后 re-commit 会丢失之前的 signoff
3. `git cherry-pick` 不保留 signoff，需要显式 `--signoff`
4. GitHub PR 的 DCO check 检查 **所有** commit，不只是最新一个

## Solution

```bash
# 正确做法：reset --hard 到干净 base，然后 cherry-pick --signoff
git fetch upstream main
git reset --hard upstream/main
git cherry-pick <your-commit> --signoff
git push fork branch --force

# 验证：PR 应该只有 1 个 commit
gh api repos/UPSTREAM/REPO/pulls/NUMBER/commits --jq 'length'
```

## Key Points

- `git reset --soft main` 不够——soft reset 会保留旧 commit 的 parent 关系
- 必须用 `git reset --hard upstream/main` 彻底切断
- Cherry-pick 后用 `git log --oneline main..branch` 确认只有 1 个 commit
- DCO check 失败时，先查 `gh api pulls/NUMBER/commits` 确认 commit 数量

**Why:** DCO 是开源项目的硬性要求，signoff 丢失会导致 PR 无法合并
**How to apply:** Force push 后必须验证 PR commit 数量和 signoff 状态


## Verification

```bash
git log --format="%b" -1 | grep -i "Signed-off-by" || echo none
```

**Expected Output:**
```
Signed-off-by:
```
