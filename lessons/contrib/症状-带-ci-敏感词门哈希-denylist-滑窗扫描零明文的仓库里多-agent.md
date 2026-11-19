---
title: "症状 带 CI 敏感词门（哈希 denylist 滑窗扫描，零明文）的仓库里，多 agent 会话按「同步/推送仓库」的指令直接 `git push`，把本地积"
domain: "mcp"
tags:
  - "git"
  - "ci"
  - "denylist"
status: "published"
evidence_level: "E1"
created: "2026-11-19"
updated: "2026-11-19"
source: "intake-5226"
summary_plain: "带 CI 敏感词门（哈希 denylist 滑窗扫描，零明文）的仓库里，多 agent 会话按「同步/推送仓库」的指令直接 `git…"
trigger: "sweep denylist 窗口命中 SENSITIVE-SWEEP-FAIL push 未推提交 泄内部名"
verify: "发 issue/推送前对文本跑 denylist 滑窗扫描输出 CLEAN；推送后 CI 敏感词门绿。 推送前 python tools/sweep.py --quiet 输出 CLEAN（或仅剩已豁免项）；推送后 CI 敏感词门通过；origin/main 对照无命中。"
provenance:
  issue: "#5226"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

带 CI 敏感词门（哈希 denylist 滑窗扫描，零明文）的仓库里，多 agent 会话按「同步/推送仓库」的指令直接 `git push`，把本地积压的未推提交泄到公网——其中含内部机型名/内部项目名（工作注释、工位名、截图说明里带出）。扫描器报 `窗口命中(len=N @ offset)` + `SENSITIVE-SWEEP-FAIL`，CI 必挂。

## Root Cause

未推历史是**有意扣留**的：敏感串（内部机型名/项目名）随文档/注释进了提交，origin/main 一直是 CLEAN 的（对照可证）——没推是识门之举，不是遗漏。新会话看到「本地积压 N 个未推提交 + 仓库要同步」，极易把扣留误判成欠账。

## Fix

推送/同步前先跑敏感词扫描（本例 `python tools/sweep.py`）；命中就**反查子串**：对命中偏移做滑窗、逐窗哈希比对 denylist，可还原命中词（denylist 零明文但文件里词就在磁盘上）；`git show origin/main:<file>` 对照确认引入区间。命中期间不推远端；要推先脱敏+历史改写（改写历史须人拍板）。对外内容（issue/评论）发出前同样过一遍扫描。

## Verification

发 issue/推送前对文本跑 denylist 滑窗扫描输出 CLEAN；推送后 CI 敏感词门绿。

推送前 python tools/sweep.py --quiet 输出 CLEAN（或仅剩已豁免项）；推送后 CI 敏感词门通过；origin/main 对照无命中。
