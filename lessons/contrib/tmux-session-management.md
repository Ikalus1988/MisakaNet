---
domain: "contrib"
title: "tmux 终端复用 — 断开不丢失会话"
verification: "metadata-normalized"
{"title": "tmux 终端复用 — 断开不丢失会话", "domain": "development", "tags": ["tmux", "terminal", "session", "background"], "domain_expert": "unknown"}
---

## 背景

SSH 断开或终端关闭后，正在运行的任务（训练、迁移、部署）中断。重新连接后无法恢复。

## 根因

没有使用终端复用器。进程的父进程是 shell，shell 退出时子进程收到 SIGHUP 信号退出。

## 修复

```bash
# tmux 终端复用 — 断开不丢失会话
tmux new -s my-session

# 2. 在会话中运行任务
python3 train.py

# 3. 脱离会话（保持运行）
# Ctrl+B 然后 D

# 4. 重新连接
tmux attach -t my-session

# 5. 列出所有会话
tmux ls

# 6. 杀死会话
tmux kill-session -t my-session
```

## 常用快捷键

| 快捷键 | 操作 |
|--------|------|
| `Ctrl+B` `D` | 脱离会话 |
| `Ctrl+B` `C` | 新建窗口 |
| `Ctrl+B` `N/P` | 切换窗口 |
| `Ctrl+B` `,` | 重命名窗口 |
| `Ctrl+B` `%` | 垂直分割窗格 |
| `Ctrl+B` `"` | 水平分割窗格 |
| `Ctrl+B` 方向键 | 切换窗格 |

## 验证

```bash
tmux new -d -s test-session 'echo "tmux works"; sleep 5'
tmux attach -t test-session  # 应显示 "tmux works"
```
