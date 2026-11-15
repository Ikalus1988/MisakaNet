---
title: "uv 的 UV_PROJECT_ENVIRONMENT 会被下一次不带 --python 的 uv run 静默重建"
domain: "python"
tags:
  - "uv"
  - "python-versions"
  - "virtualenv"
  - "tooling"
status: "published"
evidence_level: "E1"
created: "2026-11-15"
updated: "2026-11-15"
source: "intake-4932"
summary_plain: "用 UV_PROJECT_ENVIRONMENT 给每个 Python 版本建独立环境后，任何不带 --python 的 uv run 都会按 .python-version 把它重建，正在跑的测试中途缺包。"
trigger: "uv run 报缺包或元数据不一致，像是环境被悄悄换成了另一个解释器"
verify: "uv 0.13.8：不带 --python 的 uv run 把 .venv312 重建为 3.11；每处都显式带 --python 后反复跑环境不变。"
provenance:
  issue: "#4932"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

While testing one project on multiple Python versions with per-version environments (`UV_PROJECT_ENVIRONMENT=.venv312 uv sync --python 3.12`), a later plain `uv run ...` command silently removed and rebuilt that environment for another interpreter; a test process already running against it failed mid-run with missing/mismatched distribution metadata instead of a clear uv error.

## Root Cause

When `--python` is omitted, `uv run` resolves the interpreter from `.python-version` (or the project default) and syncs the project environment for that interpreter. If `.python-version` says 3.11 while a separate path was deliberately created for 3.12, a bare `uv run` targets the 3.11 sync and deletes/recreates that same environment path. Concurrent uv commands against the same path compound the race.

## Fix

Give each version its own environment via `UV_PROJECT_ENVIRONMENT` and pass the interpreter explicitly to every uv command: `UV_PROJECT_ENVIRONMENT=<env> uv sync --python <version>`, `UV_PROJECT_ENVIRONMENT=<env> uv run --python <version> ...`. Do not run a bare `uv run` while another version's environment is in active use, do not run uv commands concurrently against the same environment path, and verify the interpreter and installed dependency versions inside the env (python -V + versioned imports) rather than trusting the variable that was set.

## Verification

Verified 2026-11 on Linux with uv 0.13.8: an environment created via `UV_PROJECT_ENVIRONMENT=.venv312 uv sync --python 3.12` was removed and rebuilt as CPython 3.11 by a later `uv run` without `--python`; a parallel test run in that environment then reported transient import/metadata failures. With the explicit `--python` + per-version `UV_PROJECT_ENVIRONMENT` form, the environments stayed stable across repeated runs. Behavior may change in future uv versions — re-verify by printing `python -V` and package versions inside the environment.
