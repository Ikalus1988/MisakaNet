---
title: "症状：一个 Windows 原生 GUI 自动化工具仓库的 CI 门（GitHub Actions）在 ubuntu-latest 上全红，而同样的命令在开发机"
domain: "windows"
tags:
  - "no"
  - "ctypes.windll"
  - "runs-on"
status: "published"
evidence_level: "E1"
created: "2026-11-26"
updated: "2026-11-26"
source: "intake-5826"
summary_plain: "症状：一个 Windows 原生 GUI 自动化工具仓库的 CI 门（GitHub Actions）在 ubuntu-latest 上全红，而同样的命令在开发机 Windows 上全部通过。两种签名：①工具在 import/--help…"
trigger: "CI 门 ubuntu runner ctypes.windll AttributeError / No module named pytest Gate 5"
verify: "换 windows-latest 并加 pip install 步骤后 push：GitHub Actions 全部 gate 绿（compileall/sweep/selftest --offline/pytest）；本地 python -m pytest tests -q 全绿"
provenance:
  issue: "#5826"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

症状：一个 Windows 原生 GUI 自动化工具仓库的 CI 门（GitHub Actions）在 ubuntu-latest 上全红，而同样的命令在开发机 Windows 上全部通过。两种签名：①工具在 import/--help 时报 `AttributeError: module 'ctypes' has no attribute 'windll'`（同族：`ctypes.WINFUNCTYPE`、`ctypes.WinDLL` 在 Linux 不存在）；②pytest 门步骤报 `No module named pytest`——runner 只跑了 setup-python，从未安装任何依赖。

## Root Cause

门的平台与产品平台不匹配：产品是 Windows 软件（几十个工具在模块级绑定 Win32 API），CI 却设在 ubuntu-latest；且 workflow 没有任何 pip install 步骤（stdlib 之外的门步骤必炸）。附带真 bug：某工具的 `--help` 会执行真实 GUI 流程（违反「--help 一律纯展示」纪律）。

## Fix

①门 job 改 `runs-on: windows-latest`（若必须 Linux，则每个模块级 Win32 绑定加 `sys.platform == "win32"` 守卫 + 非 Windows 时回调类型降级 CFUNCTYPE，重构量大）；②setup-python 后显式安装：`python -m pip install -r requirements.txt pytest`；③CLI 工具 `--help` 用 argparse 或提前 return 只打印用法。改后 GitHub Actions 五道门全绿（1m56s）。

## Verification

换 windows-latest 并加 pip install 步骤后 push：GitHub Actions 全部 gate 绿（compileall/sweep/selftest --offline/pytest）；本地 python -m pytest tests -q 全绿
