---
title: Hermes Agent 手动更新步骤（update 超时）
domain: devops
subdomain: hermes
source: bootstrap
status: draft
tags: ["project:agent-medici", "severity:medium", "node:hermes_wsl"]
confidence: 0.8
created: 2026-05-03
---

## 问题

hermes update 因为 git 分叉（diverged branches）或 uv 超时而失败。

## 根因

Hermes Agent 装在 ~/.hermes/ 目录下，update 命令内部执行 git pull + uv sync。
当本地分支与远程分叉（如因 force push），或 uv 下载包超时时，update 卡死或报错。

## 修复

手动更新步骤：
```bash
cd ~/.hermes
git fetch origin
git rebase origin/main     # 处理分叉
uv sync --reinstall        # 重装依赖
hermes cache clear         # 清理缓存
```

如果 git rebase 冲突：git rebase --abort → git reset --hard origin/main

## 验证

hermes --version 显示最新版本号。hermes help 正常输出。

## 场景

Hermes Agent CLI 用户，遇到 update 超时或 git 冲突。
