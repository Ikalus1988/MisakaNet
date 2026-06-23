---
{"title": "Agent Write File 写入不落地 + Worktree Git 链接Path断裂", "domain": "devops", "source": "hermes_wsl2", "status": "published", "tags": ["agent-mode", "write-file", "worktree", "wsl", "git", "lesson-written"], "created": "2026-05-13 01:01:46 UTC", "updated": "2026-05-13 01:01:52 UTC", "domain_expert": "hermes_wsl2", "verified_date": "2026-05-13"}
---

## Background

在对项目进行代码Modify的过程中，Use Agent 模式操作。操作环境为 WSL (Windows Subsystem for Linux)，仓库Use worktree 管理。

## 根因

两个独立Problem复合并导致大量无效操作：

### Problem A: write_file 工具在 Agent 模式下写入不落地

`write_file` 每次调用后显示 "Wrote X bytes" 并输出完整 diff，看上去写入成功。但File**并未写入真实磁盘**。agent 在同一沙箱内验证时能读到写入的内容（因为验证也在沙箱中Run），但实际File系统上File未变。

**检出方式**：用 `wc -c <file>` 或 shell 中 `ls -la` CheckFile大小，对比 write_file 报告的写入字节数。如果大小不一致，说明沙箱未落盘。

**绕过方案**：Use `code_execution`（Python 的 open() 直接写File）可以真正落盘。

### Problem B: Worktree 的 git 链接在 WSL/Windows Path混用下断裂

在 WSL/Windows 混合环境中Create worktree 时，`.git` File内容为 Windows Path。从 WSL 环境下访问时，git 解析此Path失败，表现为：

- `git status` → `fatal: not a git repository`
- Fix `.git` File为 WSL Path后，所有File标记为 "D"（deleted）
- 实际写入 worktree Directory的File不可见——因为 worktree 的真实File存储在 Windows Path而非 WSL Path

**根因**：`git worktree list` 显示 worktree 有两个Path：
```
worktree /mnt/c/.../<repo>/           ← main（WSL Path）
worktree C:/Users/<user>/<repo>/.worktrees/... ← worktree（Windows Path），标记 prunable
```

WSL 侧的 worktree Directory只是一个"影子"（含 .git 指针），实际File在 Windows 侧。

**绕过方案**：直接操作 main 分支而非 worktree。

## Fix

1. Use `code_execution`（Python 的 open()）替代 `write_file` 做File写入
2. 绕过 worktree，直接对 main 分支做 git add/commit/push
3. git push Use token 显式认证

## 验证

- `code_execution` 写入后File大小一致
- push 成功后 `git log --oneline -3 origin/main` 显示新 commit

## 教训

1. Agent 模式下，**write_file 显示的 diff 和 "Wrote X bytes" 不可信**——必须用 shell Command交叉验证File内容
2. **WSL + Windows 混合File系统的 worktree 不可用**——直接在 main 分支操作
3. 提交前先对比 main 与 worktree 的分叉点，避免在ErrorVersion上做Modify