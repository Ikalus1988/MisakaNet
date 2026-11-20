---
title: "gh pr create 的 --base 只能是目标仓库自己的分支：stacked PR 指不到上游另一个 PR 的 head，报 baseRefName is invalid"
domain: "mcp"
tags:
  - "user-branch"
  - "update_lessons_json.py"
  - "git"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4993"
summary_plain: "`gh pr create --base <fork-branch>` 想把 stacked PR 挂到上游仓库里另一个 PR 的 head 分支上，报错 `GraphQL: The baseRefName is invalid."
trigger: "Problem `gh pr create --base <fork-branch>` 想把 stacked PR 挂到上游仓库里另一个 PR 的 head 分. `gh pr create --base <fork-branch>` 想把 stacked PR 挂到上游仓库里另一个 PR 的 head…"
verify: "同一改动集：`gh pr create --base zsxh1990:other-branch` 必现 GraphQL 报错；改 `--base main` + cherry-pick 到新分支（生成物冲突用重跑生成器解决）后 PR 创建成功、diff 只含该批文件、CI gate 绿。"
provenance:
  issue: "#4993"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

`gh pr create --base <fork-branch>` 想把 stacked PR 挂到上游仓库里另一个 PR 的 head 分支上，报错 `GraphQL: The baseRefName is invalid. (createPullRequest)`，PR 创建失败。base 填的是 `user:branch` 形式的 fork 分支名。

## Root Cause

GitHub PR 的 baseRefName 只能是**目标仓库自己**的分支；fork 的分支（`user:branch` 或只写分支名但存在于 fork）不能当 base。跨仓 stacked PR 在 GitHub 上不存在这个形态——stacked 只对同仓库分支成立。

## Fix

1) 让第二个 PR 的分支直接 rebase/cherry-pick 到 upstream/main，独立开 PR（diff 只含自己的改动）；2) 生成物冲突不要手工合并——checkout 冲突文件后重跑生成器（`update_lessons_json.py` 等），`git add` 生成输出再继续；3) 顺序无关的两个 PR 各自基于 main，避免 stacked 依赖。

## Verification

同一改动集：`gh pr create --base zsxh1990:other-branch` 必现 GraphQL 报错；改 `--base main` + cherry-pick 到新分支（生成物冲突用重跑生成器解决）后 PR 创建成功、diff 只含该批文件、CI gate 绿。
