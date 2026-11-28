---
title: "`git push` 报： 本机其实有可用凭据：`gh` 的 keyring token 是好的，git 的 credential helper 也正是"
domain: "mcp"
tags:
  - "git"
  - "gh"
  - "using"
status: "published"
evidence_level: "E1"
created: "2026-11-28"
updated: "2026-11-28"
source: "intake-5852"
summary_plain: "`git push` 报： ``` remote: Invalid username or token."
trigger: "git github auth token gh-cli"
verify: "- `env -u GITHUB_TOKEN gh auth status` 输出里带 `Logged in to github.com account <user>`（而不是 `using token (GITHUB_TOKEN)`）； - `env -u GITHUB_TOKEN git push` 成功，且不再要求输入用户名/密码。"
provenance:
  issue: "#5852"
  source: "MCP intake (remote-agent), lesson submission converted by the maintainer"
---

## Problem

`git push` 报：

```
remote: Invalid username or token. Password authentication is not supported for Git operations.
fatal: Authentication failed for 'https://github.com/<owner>/<repo>.git/'
```

本机其实有可用凭据：`gh` 的 keyring token 是好的，git 的 credential helper 也正是
`gh auth git-credential`。 所以「凭据过期 / 需要重新登录」这条直觉是错的。

## Root Cause

**根因**：shell 环境里有一个**已失效的 `GITHUB_TOKEN`**，而 `gh` 优先读这个环境变量。

## Fix

```bash
# 1. 确认是不是它在捣乱
env -u GITHUB_TOKEN gh auth status          # 去掉变量后能看到 keyring 里的真实账号
env -u GITHUB_TOKEN git push -u origin <branch>

# 2. 长期做法：把变量从 shell 配置里去掉，或在相关命令前用 env -u
```

不要试图用「重新 `gh auth login`」解决：变量还在，`gh` 仍然优先用它。

## Verification

- `env -u GITHUB_TOKEN gh auth status` 输出里带 `Logged in to github.com account <user>`（而不是 `using token (GITHUB_TOKEN)`）；
- `env -u GITHUB_TOKEN git push` 成功，且不再要求输入用户名/密码。
