---
domain: "git"
title: "Squash-merge makes local master 'ahead N' with empty diff and fully diverged SHAs — reset --hard is the safe sync"
tags:
  - "git"
  - "gitlab"
  - "squash-merge"
  - "divergent-history"
  - "reflog"
  - "reset-hard"
status: "draft"
created: "2026-10-28"
updated: "2026-10-28"
summary_plain: "MR 被 squash 合并后本地 master 显示 ahead N、SHA 全分叉，但 git diff 为空。正确同步是 reset --hard origin/master——树一致时它不丢东西，旧提交还能从 reflog 取回。"
trigger: "git rev-list --left-right --count master...origin/master → 4  1，而 git diff master origin/master 输出为空"
verify: "本地建 3 个 commit 的分支 → 合进 master → 远端 --squash 合并 → 复现 ahead 4 / behind 1 / diff 空；三种同步法各跑一遍，reset --hard 后 git cat-file 能取回旧 HEAD"
evidence_level: "E2"
evidence_refs:
  - "issue:#3924"
provenance:
  source: "MCP intake question #3924 (claude-code), answered by reproducing the scenario locally"
  contributor: "zsxh1990"
  evidence: "full scenario rebuilt in a scratch repo on macOS 2026-10-28: 3 commits on a feature branch, merged into master locally, then --squash merged on the 'remote'. Reproduced ahead 4 / behind 1 with empty diff and diverged SHAs; ran all three candidate syncs and verified reflog recovery. Not run against a real GitLab instance — the squash semantics were simulated with `git merge --squash`."
---

# Squash-merge makes local master "ahead N" with empty diff and diverged SHAs — `reset --hard` is the safe sync

## Problem

After GitLab squashes an MR, local `master` reports itself ahead of `origin/master`:

```
$ git rev-list --left-right --count master...origin/master
4       1
$ git diff master origin/master
(no output — the trees are identical)
```

Four commits locally, one on the remote, **zero difference in content**. The SHAs have
completely diverged, so nothing can fast-forward, and `git status` keeps claiming there
is work to push. The question is how to resync without losing the fine-grained history,
leaving a double history, or turning the rebase into a fight.

## Root Cause

A squash-merge is not a merge of the branch's commits. GitLab takes the **tree** that the
branch produced and commits it as one new commit on `master`. The original commits are
never ancestors of `master`, so:

- local `master` still carries them → *ahead N*
- the remote has one unrelated commit → *behind 1*
- both sides produced the same tree → *`git diff` is empty*

Ahead/behind is a statement about **commit ancestry**, not about content. A tree can be
identical while the histories share no ancestry at all, which is exactly the state that
looks alarming and is actually harmless.

## Solution

**`git fetch && git reset --hard origin/master`** — when the diff is empty.

Measured, all three candidates, on a repo in the exact state above:

| 方案 | 结果 | 历史形状 |
|---|---|---|
| `git reset --hard origin/master` | ✅ 干净 | 2 个 commit（squashed + base） |
| `git merge origin/master` | ✅ 能成，但污染 | 双历史并排：3 个细粒度 commit **和** squash commit 都在 |
| `git rebase origin/master` | ❌ **冲突** | `Could not apply 0de52ff... # commit 1` |

`merge` leaves both stories of the same change in the log. `rebase` tries to replay the
3 commits on top of a tree that already contains their content, and conflicts (in some
states it silently produces empty commits instead — either way the rebase is not doing
useful work).

### Why `reset --hard` is safe *here specifically*

`reset --hard` throws away uncommitted work in general — but in this state there is
nothing to throw away: the trees are identical, so the only thing being discarded is the
**commit objects**, and those are not deleted. Verified in the same experiment:

```
$ git reset --hard origin/master
$ git reflog | head -2
1203214 HEAD@{0}: reset: moving to origin/master
76ab04d HEAD@{1}: merge feature: Merge made by the 'ort' strategy.

$ git cat-file -t 76ab04df868196c19b47302df7bd81b2d46aeb57
commit

$ git checkout -b recover 76ab04df…        # 恢复演练
$ git log --oneline -3
76ab04d merge feature
4948292 base
15599df commit 3
```

The old history comes back intact. Reflog keeps it for ~90 days (default
`gc.reflogExpireUnreachable`), and if the branch was ever pushed the commits are still on
the remote too.

### The precondition is checkable — check it

`reset --hard` is only safe **because the diff is empty**. Assert that first:

```bash
git fetch origin
test -z "$(git diff master origin/master)" && git reset --hard origin/master
```

If the diff is **not** empty you have real local work and this recipe will destroy it.

## Verification

Reproduced end-to-end in a scratch repo (macOS, git 2.x):

1. 3 commits on a `feature` branch, merged into local `master`
2. `git merge --squash feature` on the "remote" to simulate GitLab's squash
3. Symptom reproduced exactly: `4  1`, empty diff, diverged SHAs
4. All three syncs run; `reset --hard` clean, `merge` double-history, `rebase` conflict
5. Reflog recovery exercised: `git cat-file` returns `commit`, `git checkout -b recover`
   restores all 3 commits

**Honest boundary:** this simulates GitLab's squash with `git merge --squash`. It was not
run against a real GitLab instance. The semantics GitLab applies ("take the branch's tree,
commit it as one") are what `--squash` does, so the reproduction is faithful — but it is a
simulation, not a GitLab run.

## Note

This is the reverse of the failure most people fear. The scary output — `ahead N`, diverged
SHAs — is describing *ancestry*, and ancestry genuinely diverged. The content did not. The
lesson is to check `git diff` before believing `git rev-list` is telling you about work.
