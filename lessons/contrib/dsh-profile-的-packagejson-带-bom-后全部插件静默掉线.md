---
title: "DSH profile 的 package.json 带 BOM 后，全部插件静默掉线"
domain: "windows"
tags:
  - "dsh"
  - "windows"
  - "powershell"
  - "utf8"
  - "bom"
  - "package-json"
  - "plugin-loader"
status: "published"
evidence_level: "E1"
created: "2026-11-01"
updated: "2026-11-01"
source: "intake-4240"
summary_plain: "在 Windows 上用 PowerShell 改 DSH profile 的 package.json，写入了 UTF-8 BOM，重启后全部插件静默掉线（installed 为空）。"
trigger: "DSH profile 的 package.json 带 BOM 后，全部插件静默掉线. Windows PowerShell 5.1 的 Set-Content -Encoding UTF8 / Out-File 默认写 BOM，加载器把整份配置判为损坏。"
verify: "重启宿主后插件列表恢复；用 [IO.File]::ReadAllBytes(package.json) 检查前三字节不是 EF BB BF。"
provenance:
  issue: "#4240"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

在 Windows 上用 PowerShell 编辑 DeepSeek Harness (DSH) profile 的 package.json（例如给 dsh.profile.bundles 加插件），改完重启宿主，所有插件消失：已安装列表为空（installed: {}），宿主本身能起但没有任何插件加载，也没有指向配置错误的具体报错。

## Root Cause

PowerShell 的 Set-Content -Encoding UTF8 / Out-File 在 Windows PowerShell 5.1 上默认写 UTF-8 BOM（EF BB BF）。DSH 的 profile 加载器把带 BOM 的 package.json 判定为损坏的配置，于是丢弃整份 profile 配置，结果不是某个插件失败而是全部插件都不挂载。

## Fix

写入时显式用不带 BOM 的编码：[IO.File]::WriteAllText($path, $json, (New-Object System.Text.UTF8Encoding(False)))，或者用 rc / edit 这类不写 BOM 的编辑器。改完先验证前三字节是 123,10,32（'{' + 换行 + 空格）再重启。

## Verification

重启宿主后插件列表恢复；用 [IO.File]::ReadAllBytes(package.json) 检查前三字节不是 EF BB BF。
