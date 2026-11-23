---
title: "ops_bash 连续两次报 EXECUTOR_UNAVAILABLE：`the restricted Bash runtime could not be pr"
domain: "windows"
tags:
  - "python"
  - "job_kill"
  - "git"
status: "published"
evidence_level: "E1"
created: "2026-11-23"
updated: "2026-11-23"
source: "intake-5603"
summary_plain: "ops_bash 连续两次报 EXECUTOR_UNAVAILABLE：`the restricted Bash runtime could not be prepared: UNKNOWN: unknown error, link…"
trigger: "EXECUTOR_UNAVAILABLE the restricted Bash runtime could not be prepared UNKNOWN unknown error link winuxcmd od.exe"
verify: "job_kill 掉长驻 bash 后台任务后，同一条 ops_bash 命令返回 exit code 0（本次 `git status --short` 成功）。"
provenance:
  issue: "#5603"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

ops_bash 连续两次报 EXECUTOR_UNAVAILABLE：`the restricted Bash runtime could not be prepared: UNKNOWN: unknown error, link '<PATH>' -> '...\od.exe'`（重试后变成 awk.exe）。文件工具（ops_read_files/ops_grep/write）同时正常，只有 shell 子进程失败。当时有一个 run_in_background 的 `python -m http.server` 长任务在跑。

## Root Cause

dsh-ops 的 niubash 每次执行都要把 winuxcmd 私有副本 hardlink 到新的 Temp 执行树；在 Windows 上存在链接计数/并发竞争（错误文案自己写了「For link-count mismatches from 0.5.1, upgrade dsh-ops to 0.5.2 or later; retries and cache cleanup do not fix that concurrency bug」）。长驻 bash job 占着执行树，新执行树的 hardlink 复制更容易失败。

## Fix

先 `job_kill` 掉所有长驻 bash 后台任务，再重试 ops_bash——本次成功后立即恢复正常。长期解法是把 dsh-ops 升到 0.5.2+；不要靠反复重试或清缓存。

## Verification

job_kill 掉长驻 bash 后台任务后，同一条 ops_bash 命令返回 exit code 0（本次 `git status --short` 成功）。
