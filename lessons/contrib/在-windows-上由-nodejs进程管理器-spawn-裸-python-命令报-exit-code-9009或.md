---
title: "在 Windows 上由 Node.js/进程管理器 spawn 裸 `python` 命令，报 exit code 9009（或 ENOENT），但手动在终端"
domain: "windows"
tags:
  - "python"
  - "py"
  - "where"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-5068"
summary_plain: "在 Windows 上由 Node.js/进程管理器 spawn 裸 `python` 命令，报 exit code 9009（或 ENOENT），但手动在终端敲 python 是正常的。"
trigger: "在 Windows 上由 Node.js/进程管理器 spawn 裸 `python` 命令，报 exit code 9009（或 ENOENT），但手动在终端. 但手动在终端敲 python 是正常的。"
verify: "spawn 绝对路径后退出码为 0，不再出现 9009；`where python` 与 spawn 所用路径一致。"
provenance:
  issue: "#5068"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

在 Windows 上由 Node.js/进程管理器 spawn 裸 `python` 命令，报 exit code 9009（或 ENOENT），但手动在终端敲 python 是正常的。

## Root Cause

裸 `python` 被 Windows 的 App Execution Aliases 解析到 Microsoft Store 存根（python.exe 的 0 字节转发壳），spawn 它不会触发 Store 安装且直接失败；手动终端可能因为 PATH 顺序/交互式解析不同而正常。必须用绝对路径（如已捆绑的解释器完整路径）或 `py` launcher。

## Fix

1. 用解释器的完整绝对路径 spawn（如 `<bundle><PATH>`），不要用裸 `python`；
2. 或关闭「应用执行别名」里的 python.exe/pip.exe 开关；
3. 传参加 `-X utf8` 避免 Windows 默认代码页乱码。

## Verification

spawn 绝对路径后退出码为 0，不再出现 9009；`where python` 与 spawn 所用路径一致。
