---
{"title": "Git 合并冲突处理 — 手动解决最佳实践", "domain": "development", "source": "unknown", "status": "draft", "tags": ["git", "merge", "conflict", "rebase"], "created": "2026-06-12 18:46:23 UTC", "updated": "2026-06-12 18:46:23 UTC"}
---


## 背景

`git pull` 或 `git merge` 时报 `CONFLICT`，文件里出现 `<<<<<<<` 标记。不知如何选择。

## 根因

两个分支修改了同一文件的同一区域。Git 无法自动决定保留哪个版本。

## 修复

```bash
# 1. 查看哪些文件有冲突
git status

# 2. 查看冲突详情
git diff

# 3. 查看每个冲突文件的双方版本
git checkout --ours filename.py   # 保留当前分支的版本
git checkout --theirs filename.py # 保留合并进来的版本

# 4. 手动编辑（推荐）：打开冲突文件，找 <<<<<<< 标记
# <<<<<<< HEAD
# 你的修改
# =======
# 对方的修改
# >>>>>>> branch-name
# 
# 保留需要的部分，删除标记线

# 5. 标记为已解决
git add filename.py

# 6. 完成合并
git commit  # 使用自动生成的合并信息

# 7. 如果后悔了，取消合并
git merge --abort
```

## 预防

```bash
# 拉取前先 rebase 减少冲突
git pull --rebase

# 频繁提交 + 频繁推送，减少差异量
```
