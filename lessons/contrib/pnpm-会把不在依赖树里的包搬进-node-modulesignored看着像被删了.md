---
title: "pnpm 会把不在依赖树里的包搬进 node_modules/.ignored，看着像被删了"
domain: "windows"
tags:
  - "pnpm"
  - "node-modules"
  - "ignored"
  - "dependency-tree"
  - "package-json"
status: "published"
evidence_level: "E1"
created: "2026-11-02"
updated: "2026-11-02"
source: "intake-4247"
summary_plain: "手动放进 node_modules 的包，或者刚下载但没写进 package.json dependencies 的包，在下一次 pnpm install/add 之后原地消失。"
trigger: "pnpm 会把不在依赖树里的包搬进 node_modules/.ignored，看着像被删了. 手动放进 node_modules 的包，或者刚下载但没写进 package.json dependencies 的包，在下一次 pnpm install/add 之后原地消失。"
verify: "再跑一次 pnpm install，包还在原位；日志里不再出现 Moving ... to .ignored。"
provenance:
  issue: "#4247"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

手动放进 node_modules 的包，或者刚下载但没写进 package.json dependencies 的包，在下一次 pnpm install/add 之后原地消失。

## Root Cause

pnpm 以 package.json 的依赖树为准，发现 node_modules 里有它不认识的包就搬走，日志里是一条 WARN: Moving <pkg> to node_modules/.ignored，不报错。

## Fix

包必须写进 package.json 的 dependencies 才算数；临时塞进去的东西被搬走后从 .ignored 里取回或重新 add。

## Verification

再跑一次 pnpm install，包还在原位；日志里不再出现 Moving ... to .ignored。
