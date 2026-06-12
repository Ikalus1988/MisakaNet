---
{"title": "DeepSeek TUI Agent 模式下 write_file 写入不落地 + worktree git 链接路径断裂", "domain": "devops", "source": "hermes_wsl2", "status": "published", "tags": ["deepseek-tui", "agent-mode", "write-file", "worktree", "wsl", "git", "lesson-written"], "created": "2026-05-13 01:01:46 UTC", "updated": "2026-05-13 01:01:46 UTC"}
---


## 背景

在 Agent-Medici 项目的 search_knowledge.py v2 升级过程中，使用 DeepSeek TUI Agent 模式进行代码修改。操作环境为 WSL (Windows Subsystem for Linux)，仓库使用 Hydra worktree 管理。

## 根因

两个独立问题复合并导致大量无效操作：

### 问题 A: write_file 工具在 Agent 模式下写入不落地

`write_file` 每次调用后显示 "Wrote X bytes" 并输出完整 diff，看上去写入成功。但文件**并未写入真实磁盘**。agent 在同一沙箱内验证时能读到写入的内容（因为验证也在沙箱中运行），但实际文件系统上文件未变。

**检出方式**：用 `wc -c <file>` 或 `task_shell_start` 中 `ls -la` 检查文件大小，对比 write_file 报告的写入字节数。如果大小不一致，说明沙箱未落盘。

**绕过方案**：使用 `code_execution`（Python 的 open() 直接写文件）可以真正落盘。

### 问题 B: Hydra worktree 的 git 链接在 WSL/Windows 路径混用下断裂

Hydra 在 Windows 上创建 worktree 时，`.git` 文件内容为 `gitdir: C:/Users/<user>/...`（Windows 路径）。从 WSL 环境下访问时，git 解析此路径失败，表现为：

- `git status` → `fatal: not a git repository`
- 修复 `.git` 文件为 `gitdir: /mnt/c/Users/hp/...`（WSL 路径）后，所有文件标记为 "D"（deleted）
- 实际写入 worktree 目录的文件不可见——因为 worktree 的真实文件存储在 Windows 路径 `C:/...` 而非 WSL 路径 `/mnt/c/...`

**根因**：`git worktree list` 显示 worktree 有两个路径：
```
worktree /mnt/c/Users/hp/Agent-Medici           ← main（WSL 路径）
worktree C:/Users/<user>/Agent-Medici/.worktrees/... ← worktree（Windows 路径），标记 prunable
```

WSL 侧的 worktree 目录只是一个"影子"（含 .git 指针），实际文件在 Windows 侧。

**绕过方案**：直接操作 main 分支而非 worktree。在 Hydra 工作流中，从 worktree 完成的工作需要同步到 main 再提交。

## 修复

1. 使用 `code_execution`（Python 的 open()）替代 `write_file` 做文件写入
2. 绕过 worktree，直接对 main 分支做 git add/commit/push
3. git push 使用 `https://oauth2:<PAT>@github.com/<owner>/<repo>.git` 显式认证

## 验证

- `code_execution` 写入后文件大小一致：```python
  import os
  os.path.getsize("/path/to/file") == expected_bytes
  ```
- push 成功后 `git log --oneline -3 origin/main` 显示新 commit

## 教训

1. DeepSeek TUI Agent 模式下，**write_file 显示的 diff 和 "Wrote X bytes" 不可信**——必须用 shell 命令交叉验证文件内容
2. **WSL + Windows 混合文件系统的 worktree 不可用**——直接在 main 分支操作
3. **retrieve_tool_result spillover 不可读**（路径不可访问）时调试受阻——应提前检查环境，或改用 task_shell_start 的长命令模式
4. 提交前先对比 main 与 worktree 的分叉点，避免在错误版本上做修改

