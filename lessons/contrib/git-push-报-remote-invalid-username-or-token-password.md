---
title: "`git push` 报 `remote: Invalid username or token. Password authentication is not"
domain: "mcp"
tags:
  - "git"
  - "gh"
  - "using"
status: "published"
evidence_level: "E1"
created: "2026-11-26"
updated: "2026-11-26"
source: "intake-5841"
summary_plain: "`git push` 报 `remote: Invalid username or token."
trigger: "git push 报 Authentication failed，但用户说之前能推，gh auth status 出现 using token (GITHUB_TOKEN)"
verify: "同一条 gh auth status：带 GITHUB_TOKEN 时打 `using token (GITHUB_TOKEN)` 且失败，`env -u GITHUB_TOKEN` 后打 `✓ Logged in ... (keyring)` 并列出 repo scope；随后 git push 返回 200 而不是 Authentication failed"
provenance:
  issue: "#5841"
  source: "MCP intake (cindy), lesson submission converted by the maintainer"
---

## Problem

`git push` 报 `remote: Invalid username or token. Password authentication is not supported`，但本机其实有可用凭据：`gh` 的 keyring token 有效，`credential.https://github.com.helper` 就是 `gh auth git-credential`。

## Root Cause

环境里有一个**失效的 `GITHUB_TOKEN`**，`gh` 优先读它，于是两头一起坏：`gh auth status` 报 `using token (GITHUB_TOKEN)` 看起来像没登录；git 的 credential helper 正是 gh，坏 token 被交给 git，`git push` 一起失败。症状与"凭据过期"完全相同，只查 `~/.git-credentials` 会误判（那里常存着更早的失效 PAT）。

## Fix

```bash
env -u GITHUB_TOKEN gh auth status
env -u GITHUB_TOKEN git push -u origin <branch>
```
先确认 gh 用哪份凭据，再怀疑 token 本身。

## Verification

同一条 gh auth status：带 GITHUB_TOKEN 时打 `using token (GITHUB_TOKEN)` 且失败，`env -u GITHUB_TOKEN` 后打 `✓ Logged in ... (keyring)` 并列出 repo scope；随后 git push 返回 200 而不是 Authentication failed
