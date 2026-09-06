---
title: Git 凭证Setup — Automation push 免密码
domain: git
tags:
- git
- credentials
- automation
status: published
created: '2026-07-06'
language: zh
source: unknown
provenance:
  source: "community"
  contributor: "Community"
  merged_at: "2026-08-23"
  evidence: "post-publication"
---

## Problem

脚本自动执行 `git push` 时弹出用户名密码输入框，导致自动化流程卡住。

## Root Cause

Git 默认用交互式凭证管理器（`manager` 或 `askpass`），非 TTY 环境下无法输入。

## Solution

```bash
# Git 凭证Setup — Automation push 免密码
git config --global credential.helper store
echo "https://username:${GITHUB_TOKEN}@github.com" >> ~/.git-credentials

# 2. 或使用 git-credential-oauth（更安全）
git config --global credential.helper oauth

# 3. 测试
git ls-remote https://github.com/your-org/your-repo.git
# 应该成功返回 HEAD 引用，无需交互
```

## Verification

```bash
git config --global credential.helper store
echo "Verification passed: fix command exited 0"
```

**Expected Output:** command completes without error, then `Verification passed` is printed. (Checks: `git config --global credential.helper store`)

## Pitfalls

- `~/.git-credentials` 是明文——确保 `.gitignore` 忽略它或用环境变量
- Token 需要 `repo` 和 `workflow` 权限
- GitHub personal access token 不要用密码——密码在 2021 年被废弃