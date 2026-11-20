---
title: "cherry-pick 改了源文件的提交时派生物必然冲突：冲突的是生成结果而不是手写内容，要重跑生成链而不是逐块解"
domain: "mcp"
tags:
  - "git"
  - "cherry"
  - "pick"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4994"
summary_plain: "cherry-pick 一个改了源文件（如 lessons/*.md）的提交到新分支时，仓库里提交过的派生物（data/lessons.json、index、snapshot…"
trigger: "Problem cherry-pick 一个改了源文件（如 lessons/*.md）的提交到新分支时，仓库里提交过的派生物（data/lessons.json. cherry-pick 一个改了源文件（如…"
verify: "cherry-pick 后 `git diff <base> --stat` 只显示本批源文件 + 重新生成的派生物（行数与单批一致）；随后跑仓库 gate/测试（如 lesson_gate.py、断言\"生成器对不变语料是 no-op\"的测试）全绿。"
provenance:
  issue: "#4994"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

cherry-pick 一个改了源文件（如 lessons/*.md）的提交到新分支时，仓库里提交过的派生物（data/lessons.json、index、snapshot 等）全部冲突（UU），手工逐块合并既慢又容易把上一批的派生内容带进新分支。

## Root Cause

派生物由源文件生成且提交进仓库；两个并行分支各自重新生成过，cherry-pick 时生成物三方合并必冲突——冲突的是"生成结果"而不是"手写内容"，手工解是拿错了杠杆。

## Fix

生成物冲突不手工合并：`git checkout --theirs`（或直接丢弃）冲突的派生文件 → 重跑仓库的生成器脚本 → `git add -A` 后 `git cherry-pick --continue`。生成器是唯一正确来源，重跑保证派生物与本分支源文件严格一致，不会混入另一分支的生成结果。

## Verification

cherry-pick 后 `git diff <base> --stat` 只显示本批源文件 + 重新生成的派生物（行数与单批一致）；随后跑仓库 gate/测试（如 lesson_gate.py、断言"生成器对不变语料是 no-op"的测试）全绿。
