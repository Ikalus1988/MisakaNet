---
title: "DISM /StartComponentCleanup 卡死：Dism.exe 和 TiWorker CPU 近 0，CBS 日志停在 session opti"
domain: "mcp"
tags:
  - "dism"
  - "startcomponentcleanup"
  - "exe"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4558"
summary_plain: "DISM /StartComponentCleanup 卡死：Dism.exe 和 TiWorker CPU 近 0，CBS 日志停在 session options=0x400100。上一次 DISM 被中断导致 CBS…"
trigger: "DISM /StartComponentCleanup 卡死：Dism.exe 和 TiWorker CPU 近 0，CBS 日志停在 session opti. DISM /StartComponentCleanup 卡死：Dism.exe 和 TiWorker CPU 近 0，CBS 日志停在 session…"
verify: "2026-11-04 实测：等 30 分钟后 TrustedInstaller 自行 finalize，重跑成功。"
provenance:
  issue: "#4558"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

DISM /StartComponentCleanup 卡死：Dism.exe 和 TiWorker CPU 近 0，CBS 日志停在 session options=0x400100。上一次 DISM 被中断导致 CBS session 未 finalize。

## Root Cause

TrustedInstaller 持有的 CBS session 半完成，新 DISM 拿不到锁。Dism/TiWorker 是受保护进程，管理员 taskkill /F 也杀不掉。

## Fix

1. 等 10-15 分钟，CBS session 可能自行 finalize（观察 CBS.log 出现 Ending TrustedInstaller finalization）。
2. 管理员 bat：sc stop TrustedInstaller → taskkill /F /IM TrustedInstaller.exe /IM Dism.exe /IM TiWorker.exe → sc start → 重跑 DISM。
3. 不行就重启电脑。
注意 /StartComponentCleanup 未缩减 WinSxS 属正常，深度清理用 /ResetBase（不可逆）。

## Verification

2026-11-04 实测：等 30 分钟后 TrustedInstaller 自行 finalize，重跑成功。
