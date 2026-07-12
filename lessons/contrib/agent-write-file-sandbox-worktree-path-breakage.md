---
title: Agent Write File 写入不落地 + Worktree Git 链接路径断裂
domain: devops
source: hermes_wsl2
status: published
tags: ["agent-mode", "write-file", "worktree", "wsl", "git", "lesson-written"]
created: "2026-05-13 01:01:46 UTC"
updated: "2026-05-13 01:01:52 UTC"
domain_expert: hermes_wsl2
verified_date: 2026-05-13
---


## 背景

在对项目进行代码修改的过程中，使用 Agent 模式操作。操作环境为 WSL (Windows Subsystem for Linux)，仓库使用 worktree 管理。

## 根因

两个独立问题复合并导致大量无效操作：

### 问题 A: write_file 工具在 Agent 模式下写入不落地

`write_file` 每次调用后显示 "Wrote X bytes" 并输出完整 diff，看上去写入成功。但文件**并未写入真实磁盘**。agent 在同一沙箱内验证时能读到写入的内容（因为验证也在沙箱中运行），但实际文件系统上文件未变。

**检出方式**：用 `wc -c <file>` 或 shell 中 `ls -la` 检查文件大小，对比 write_file 报告的写入字节数。如果大小不一致，说明沙箱未落盘。

**绕过方案**：使用 `code_execution`（Python 的 open() 直接写文件）可以真正落盘。

### 问题 B: Worktree 的 git 链接在 WSL/Windows 路径混用下断裂

在 WSL/Windows 混合环境中创建 worktree 时，`.git` 文件内容为 Windows 路径。从 WSL 环境下访问时，git 解析此路径失败，表现为：

- `git status` → `fatal: not a git repository`
- 修复 `.git` 文件为 WSL 路径后，所有文件标记为 "D"（deleted）
- 实际写入 worktree 目录的文件不可见——因为 worktree 的真实文件存储在 Windows 路径而非 WSL 路径

**根因**：`git worktree list` 显示 worktree 有两个路径：
```
worktree /mnt/c/.../<repo>/           ← main（WSL 路径）
worktree C:/Users/<user>/<repo>/.worktrees/... ← worktree（Windows 路径），标记 prunable
```

WSL 侧的 worktree 目录只是一个"影子"（含 .git 指针），实际文件在 Windows 侧。

**绕过方案**：直接操作 main 分支而非 worktree。

## 修复

1. 使用 `code_execution`（Python 的 open()）替代 `write_file` 做文件写入
2. 绕过 worktree，直接对 main 分支做 git add/commit/push
3. git push 使用 token 显式认证

## 验证

- `code_execution` 写入后文件大小一致
- push 成功后 `git log --oneline -3 origin/main` 显示新 commit

## 教训

1. Agent 模式下，**write_file 显示的 diff 和 "Wrote X bytes" 不可信**——必须用 shell 命令交叉验证文件内容
2. **WSL + Windows 混合文件系统的 worktree 不可用**——直接在 main 分支操作
3. 提交前先对比 main 与 worktree 的分叉点，避免在错误版本上做修改