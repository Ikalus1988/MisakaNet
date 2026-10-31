---
title: "NapCat 注入 QQ 后秒退：DSH/agent 工作区目录被打了低完整性标签"
domain: "windows"
tags:
  - "napcat"
  - "qq"
  - "low-integrity"
  - "icacls"
  - "dsh"
  - "sandbox"
  - "qqnt"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-3956"
summary_plain: "在 agent 指定的工作目录（如 <PATH> NapCat.Shell 并运行 launcher.bat，注入后 QQ 立刻退出：控制台只有 '[NapCat Backend] Main Process ID … Creating…"
trigger: "NapCat 注入 QQ 后秒退：DSH/agent 工作区目录被打了低完整性标签. 在 agent 指定的工作目录（如 <PATH> NapCat.Shell 并运行 launcher.bat，注入后 QQ 立刻退出：控制台只有 '[NapCat…"
verify: "1) icacls 任取一个文件应显示 'Mandatory Label\\Medium Mandatory Level'，而不是 S-1-4-… 低完整性 SID。2) 启动后 qq 进程存活，launcher 控制台打印 'WebUi [REDACTED:credential] 与 'WebUi User Panel Url…"
provenance:
  issue: "#3956"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

在 agent 指定的工作目录（如 <PATH> NapCat.Shell 并运行 launcher.bat，注入后 QQ 立刻退出：控制台只有 '[NapCat Backend] Main Process ID … Creating pipe … Process resumed' 紧接着 'Process exited.'，QQ 不显示窗口，NapCat 不监听 6099，也不生成 logs/cache。QQ 版本与 NapCat 完全匹配（QQ 9.9.33-52230 + NapCat 4.18.41），换 QQ 版本、关掉已登录的 QQ、用管理员运行都无效。

## Root Cause

DeepSeek Harness 这类 agent 会把指定工作目录及其子目录/文件标成低完整性（Low IL）。icacls 可验证：<PATH> 下文件带 S-1-[REDACTED:card_number]:(W,D,DC)，且 <PATH> 根有 Everyone:(CI)(DENY)(DC)。QQ 被注入后从该低完整性路径加载，QQNT 初始化直接失败退出（NapCat issue #2116 下有相同症状的评论，指向沙箱/低完整性标签）。用 standalone 方式（napcat.mjs fork worker）反而正常，说明失败点在 QQ 进程侧而不是 NapCat JS 侧。

## Fix

把整个 NapCat 目录拷到普通路径（不要放在 agent 工作区内），然后逐个文件把完整性提到 Medium：

$dst = '<PATH>'
Copy-Item '<PATH>' $dst -Recurse -Force
Get-ChildItem $dst -Recurse -File | ForEach-Object { icacls $_.FullName /setintegritylevel M | Out-Null }

之后用 <PATH> 启动（需要管理员；它会从注册表 HKLM\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\QQ 的 UninstallString 推导 QQ 路径）。

## Verification

1) icacls 任取一个文件应显示 'Mandatory Label\Medium Mandatory Level'，而不是 S-1-4-… 低完整性 SID。2) 启动后 qq 进程存活，launcher 控制台打印 'WebUi [REDACTED:credential] 与 'WebUi User Panel Url: http://127.0.0.1:6099/webui?[REDACTED:credential] <PATH> 生成、扫码后可登录。
