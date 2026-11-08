---
title: "被中断的安装会留下“有目录没 package.json”的残骸：静态体检看不见，require 时才炸"
domain: "devops"
tags:
  - "node"
  - "pnpm"
  - "native-module"
  - "corrupted-install"
  - "dsh"
  - "windows"
status: "published"
evidence_level: "E1"
created: "2026-11-08"
updated: "2026-11-08"
source: "intake-4570"
summary_plain: "一个宿主插件（本地记忆插件）在重启后报“启动时没能加载”，但静态体检工具报 0 错误 0 警告，门禁预测也判定放行。逐项排查：包目录存在、入口文件存在、bundle…"
trigger: "被中断的安装会留下“有目录没 package.json”的残骸：静态体检看不见，require 时才炸. 一个宿主插件（本地记忆插件）在重启后报“启动时没能加载”，但静态体检工具报 0 错误 0 警告，门禁预测也判定放行。逐项排查：包目录存在、入口文件存在、bundle…"
verify: "目录里存在 package.json 且版本正确；`require` 成功；核心功能实测通过（例如 sqlite 打开数据库并 `PRAGMA integrity_check` 返回 ok）；重启后插件不再报“启动时没能加载”。"
provenance:
  issue: "#4570"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

一个宿主插件（本地记忆插件）在重启后报“启动时没能加载”，但静态体检工具报 0 错误 0 警告，门禁预测也判定放行。逐项排查：包目录存在、入口文件存在、bundle 补丁声明正常、豁免已配、宿主版本匹配——全都正常。最后发现真正的病因是它的原生依赖：`node_modules/better-sqlite3` 目录里只有 `prebuilds/`、`src/`、`README.md`，**没有 package.json**。插件 `require` 它时直接抛错，激活失败。

## Root Cause

安装曾被中断：为了绕开“运行中的宿主锁住原生模块”，先把该目录改名让路，随后那次 `pnpm install` 在另一个包上 `ERR_PNPM_EPERM` 崩掉，于是目标目录只复制了一半就留在原地。\n\n这类残骸特别阴，因为：\n1) 常规检查只问“目录在不在”，而它**在**；\n2) 静态体检看的是清单（deps/bundles/peer/兼容表），**不扫包内文件完整性**；\n3) 门禁只判版本声明，与文件完整性无关；\n4) 只有在 import 那一刻才暴露，而错误信息指向插件激活，不指向缺文件。

## Fix

先扫出残骸（一条命令，覆盖 scoped 包）：\n```powershell\n$nm = "<profile>\\node_modules"\nGet-ChildItem $nm -Directory -Force | Where-Object { $_.Name -notmatch "^\\.\" } | ForEach-Object {\n  if ($_.Name.StartsWith("@")) {\n    Get-ChildItem $_.FullName -Directory | ForEach-Object {\n      if (-not (Test-Path (Join-Path $_.FullName "package.json"))) { "残缺: $($_.Parent.Name)\\$($_.Name)" }\n    }\n  } elseif (-not (Test-Path (Join-Path $_.FullName "package.json"))) { "残缺: $($_.Name)" }\n}\n```\n修复：从 npm 拉同名同版本 tarball（校验 `dist.shasum`）→ 解包 → **整个目录替换**。不要指望再跑一次 `pnpm install`（可能又撞锁），也不要手写 package.json（缺的是 lib/ 与原生二进制）。\n还原后必须实测：`require("<包名>")` 成功，并让该包真干一次活（sqlite 则 `PRAGMA integrity_check`）。

## Verification

目录里存在 package.json 且版本正确；`require` 成功；核心功能实测通过（例如 sqlite 打开数据库并 `PRAGMA integrity_check` 返回 ok）；重启后插件不再报“启动时没能加载”。
