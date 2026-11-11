---
title: "CI 敏感词黑名单把敏感词写进仓库：防泄密闸自己成了泄密源"
domain: "mcp"
tags:
  - "problem"
  - "ci"
  - "grep"
status: "published"
evidence_level: "E1"
created: "2026-11-11"
updated: "2026-11-11"
source: "intake-4670"
summary_plain: "CI 敏感词黑名单把敏感词写进仓库：防泄密闸自己成了泄密源"
trigger: "CI 敏感词黑名单把敏感词写进仓库：防泄密闸自己成了泄密源"
verify: "改造前后对照：改造前 CI 配置含明文（提交被安全分类器正确拒绝）；改造后本地 sweep CLEAN、机制自检双过、CI 三道门全绿且复核放行（仓内 grep 敏感词 0 命中）。防泄密闸本身通过同一把尺子的检验。 改造前后对照：明文提交被拒 → 哈希方案 CI 全绿且仓内敏感词 0 命中"
provenance:
  issue: "#4670"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

为防止敏感字面量（口令/序列号/内部项目名等）进入代码仓，在 CI 里写「敏感词 grep 黑名单」自检门——但黑名单模式串本身就内嵌了这些敏感词，随 CI 配置提交推送后等于把它们写进仓库：防泄密闸自己成了泄密源。同类变体：把 denylist 明文文件与被检内容放在同一仓库。

## Root Cause

黑名单与被保护数据同域存放，防护工具自身未纳入防护范围；提交环节没有「工具里也不能有明文」的意识（人看扫描器配置时会把它当"防护代码"而忽略其内容敏感性）。

## Fix

哈希滑窗黑名单（sha256+长度）+ 明文生成器隔离 + 扫描器机制自检

## Verification

改造前后对照：改造前 CI 配置含明文（提交被安全分类器正确拒绝）；改造后本地 sweep CLEAN、机制自检双过、CI 三道门全绿且复核放行（仓内 grep 敏感词 0 命中）。防泄密闸本身通过同一把尺子的检验。

改造前后对照：明文提交被拒 → 哈希方案 CI 全绿且仓内敏感词 0 命中
