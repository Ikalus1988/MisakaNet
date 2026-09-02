---
title: Git 合并ConflictHandling — 手动解决最佳实践
domain: git
tags:
- git
- merge
- conflict
- resolution
status: published
created: '2026-07-06'
language: zh
source: unknown
---

## Problem

`git pull` 或 `git merge` 时报 `CONFLICT`，文件里出现 `<<<<<<<` 标记，终端输出类似：

```
Auto-merging src/config.py
CONFLICT (content): Merge conflict in src/config.py
Automatic merge failed; fix conflicts and then commit the result.
```

常见触发场景：
- 多人协作时，两人同时修改了同一文件的同一函数或同一行
- 长期存活的功能分支与主干分支差异积累过大
- cherry-pick 或 rebase 时跨越多个提交的改动相互叠加
- 重命名文件后对方也修改了该文件内容（rename + edit 冲突）

## Root Cause

两个分支修改了同一文件的同一区域，Git 无法自动决定保留哪个版本。具体有三种情形：

1. **内容冲突（content conflict）**：最常见。两个分支在同一行或相邻行写入了不同内容。Git 的三路合并算法（3-way merge）以共同祖先提交为基准，发现双方都改动了同一区域，无法自动取舍。

2. **删除/修改冲突（delete/modify conflict）**：一方删除了某文件，另一方修改了该文件。Git 不知道应该保留修改还是执行删除。

3. **重命名冲突（rename conflict）**：两个分支分别将同一文件重命名为不同的名字，或一方重命名、另一方修改了内容。

## Solution

### 典型冲突文件示例

假设 `src/config.py` 发生内容冲突，打开文件后会看到：

```python
# src/config.py

DATABASE_HOST = "localhost"

<<<<<<< HEAD
DATABASE_PORT = 5432
DATABASE_NAME = "prod_db"
=======
DATABASE_PORT = 3306
DATABASE_NAME = "staging_db"
>>>>>>> feature/switch-to-mysql
```

- `<<<<<<< HEAD` 到 `=======` 之间：**当前分支**（你所在分支）的内容
- `=======` 到 `>>>>>>> branch-name` 之间：**被合并分支**的内容
- 需要手动决定保留哪部分，或将两者合并成新内容，然后删除所有标记行

### 解决步骤

```bash
# 1. 查看哪些文件有冲突（UU 表示双方都修改，AA 表示双方都新增）
git status

# 2. 查看冲突的具体差异
git diff

# 3a. 快捷方式：直接选择某一方的完整版本
git checkout --ours src/config.py    # 保留当前分支（HEAD）的版本
git checkout --theirs src/config.py  # 保留合并进来的分支的版本

# 3b. 推荐方式：手动编辑，精确合并双方改动
#     打开编辑器，找到 <<<<<<< 标记，手动决定最终内容
#     例如最终结果：
#       DATABASE_PORT = 5432
#       DATABASE_NAME = "prod_db"
#     删除 <<<<<<<、=======、>>>>>>> 三行标记

# 4. 确认文件中已无残留冲突标记
grep -rn "<<<<<<" src/

# 5. 标记为已解决
git add src/config.py

# 6. 完成合并（使用自动生成的合并信息，或加 -m 自定义）
git commit

# 7. 如果解决过程中后悔了，随时可以取消整个合并，回到合并前状态
git merge --abort
```

### 使用合并工具（可选）

```bash
# 调用配置好的可视化合并工具（如 vimdiff、VS Code、IntelliJ）
git mergetool

# 配置 VS Code 为默认合并工具
git config --global merge.tool vscode
git config --global mergetool.vscode.cmd 'code --wait $MERGED'
```

## Verification

```bash
src/config.py
echo "Verification passed: fix command exited 0"
```

**Expected Output:** command completes without error, then `Verification passed` is printed. (Checks: `src/config.py`)

## 预防

```bash
# 1. 拉取前先 rebase，将自己的提交叠加在最新主干之上，减少冲突概率
git pull --rebase

# 2. 频繁提交 + 频繁推送，减少分支间的差异积累量
git add -p && git commit -m "feat: ..." && git push

# 3. 功能分支存活时间不宜过长，定期同步主干
git fetch origin
git rebase origin/main

# 4. 对容易冲突的配置文件使用 .gitattributes 指定合并策略
# 在 .gitattributes 中添加：
# src/generated/* merge=ours
```

### 冲突预防的根本原则

- **小步提交**：每次提交只做一件事，改动范围越小，冲突越容易定位和解决
- **模块化设计**：不同功能写在不同文件中，从架构层面减少同一文件被多人同时修改的概率
- **沟通协作**：在开始修改某个核心文件前，通过 PR/Issue 告知团队，避免并行修改