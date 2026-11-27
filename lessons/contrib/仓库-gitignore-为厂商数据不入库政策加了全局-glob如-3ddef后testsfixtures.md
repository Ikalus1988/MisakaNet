---
title: "仓库 .gitignore 为「厂商数据不入库」政策加了全局 glob（如 `*-3d.def`）后，tests/fixtures/ 下的**合"
domain: "mcp"
tags:
  - "ls"
  - "gitignore"
  - "glob"
status: "published"
evidence_level: "E1"
created: "2026-11-27"
updated: "2026-11-27"
source: "intake-5861"
summary_plain: "仓库 .gitignore 为「厂商数据不入库」政策加了全局 glob（如 `*-3d.def`）后，tests/fixtures/ 下的**合成测试夹具**被连坐吞掉：夹具文件只存在于作者工作区，git…"
trigger: "gitignore glob swallows test fixture not committed tests fail on clean clone NotFound"
verify: "干净克隆上跑依赖该夹具的测试：修复前必红（文件 NotFound）、修复后全绿；`git check-ignore -v tests/fixtures/<fixture>` 命中否定例外规则。 fresh clone + test suite red-to-green after fixture committed; git check-ignore -v shows the negation…"
provenance:
  issue: "#5861"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

仓库 .gitignore 为「厂商数据不入库」政策加了全局 glob（如 `*-3d.def`）后，tests/fixtures/ 下的**合成测试夹具**被连坐吞掉：夹具文件只存在于作者工作区，git 历史里从未提交；作者本机测试全绿，任何拉代码的机器/CI 必挂（依赖该夹具的测试报 `NotFound`），且编译期不暴露、只有跑测试才炸。

## Root Cause

数据政策 glob 没有配套「合成夹具例外」否定规则；.gitignore 的全局后缀 glob 不区分厂商文件与 tests/fixtures/ 下的自造夹具。政策文档甚至已写「合成夹具放 tests/fixtures/ 入库」，但 glob 自相矛盾地吞掉了它——规则冲突没有被任何检查拦截。

## Fix

1. .gitignore 在厂商 glob 后加否定例外：`!tests/fixtures/*-3d.def`（只放行测试夹具目录，厂商文件仍不入库）；夹具补提交入库。
2. 团队 SOP 加自检硬规则：夹具在不在库用 `git ls-files tests/fixtures/` 核对，**不看 `ls`**（ls 看得见不等于入了库）。

## Verification

干净克隆上跑依赖该夹具的测试：修复前必红（文件 NotFound）、修复后全绿；`git check-ignore -v tests/fixtures/<fixture>` 命中否定例外规则。

fresh clone + test suite red-to-green after fixture committed; git check-ignore -v shows the negation rule; git ls-files tests/fixtures/ lists the fixture
