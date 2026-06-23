---{"title": "Git 合并ConflictHandling — Manual解决最佳实践", "domain": "development", "tags": ["git", "merge", "conflict", "rebase"]}---

## Background

`git pull` 或 `git merge` 时报 `CONFLICT`，File里出现 `<<<<<<<` 标记。不知如何选择。

## 根因

两个分支Modify了同一File的同一区域。Git 无法Automatic决定保留哪个Version。

## Fix

```bash
# Git 合并ConflictHandling — Manual解决最佳实践
git status

# 2. View冲突详情
git diff

# 3. View每个冲突File的双方Version
git checkout --ours filename.py   # 保留Current分支的Version
git checkout --theirs filename.py # 保留合并进来的Version

# 4. Manual编辑（推荐）：打开冲突File，找 <<<<<<< 标记
# <<<<<<< HEAD
# 你的Modify
# =======
# 对方的Modify
# >>>>>>> branch-name
# 
# 保留Require的部分，Delete标记线

# 5. 标记为已解决
git add filename.py

# 6. 完成合并
git commit  # UseAutomatic生成的合并信息

# 7. 如果后悔了，取消合并
git merge --abort
```
## Verification

1. Follow the solution steps in order
2. Run any relevant commands or tests to confirm the fix
3. Verify the symptom no longer occurs
4. Check related logs or outputs for expected behavior


## 预防

```bash
# 拉取前先 rebase 减少冲突
git pull --rebase

# 频繁提交 + 频繁推送，减少差异量
```
