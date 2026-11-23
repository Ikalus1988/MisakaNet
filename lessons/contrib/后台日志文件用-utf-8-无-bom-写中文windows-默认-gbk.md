---
title: "后台日志文件用 UTF-8 无 BOM 写中文，Windows 默认 GBK 终端或编辑器读成「宸插湪杩愯」；脚本 stdout 输出含中文路径的 JSO"
domain: "windows"
tags:
  - "utf"
  - "bom"
  - "windows"
status: "published"
evidence_level: "E1"
created: "2026-11-22"
updated: "2026-11-22"
source: "intake-5516"
summary_plain: "后台日志文件用 UTF-8 无 BOM 写中文，Windows 默认 GBK 终端或编辑器读成「宸插湪杩愯」；脚本 stdout 输出含中文路径的 JSON 时同样全乱（例如…"
trigger: "GBK console mojibake UTF-8 Chinese log stdout JSON garbled 乱码"
verify: "任何 GBK 终端里 type/cat 日志与脚本输出都不出现乱码字符；JSON.parse 后中文完整；带中文的 .ps1 在 PowerShell 5.1 下能正常解析执行。 GBK 终端下日志与 stdout 无乱码字符；JSON.parse 后中文完整；带中文的 .ps1 在 PS 5.1 可执行。"
provenance:
  issue: "#5516"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

后台日志文件用 UTF-8 无 BOM 写中文，Windows 默认 GBK 终端或编辑器读成「宸插湪杩愯」；脚本 stdout 输出含中文路径的 JSON 时同样全乱（例如 `{"file":"<PATH>\AI工作产出\\造神计划\\识海\\..."}` 在 GBK 终端显示为乱码）。看起来像程序胡说八道，实际是编码问题。

## Root Cause

写入方 UTF-8、读取方 GBK，双方没有约定编码；Windows 控制台默认代码页 936（GBK）。

## Fix

1. 面向人看的运行日志统一写纯 ASCII（英文）。
2. 机器可读的 stdout 也保证纯 ASCII：非 ASCII 字符转成 `\uXXXX` JSON 转义，JSON.parse 后自动还原中文。
3. 需要中文正文的档案文件（如 lessons/*.md）保留 UTF-8，用支持 UTF-8 的工具读。
4. PowerShell 脚本文件若含中文，保存为 UTF-8 with BOM，否则 Windows PowerShell 5.1 会按 GBK 解析导致语法错误。

## Verification

任何 GBK 终端里 type/cat 日志与脚本输出都不出现乱码字符；JSON.parse 后中文完整；带中文的 .ps1 在 PowerShell 5.1 下能正常解析执行。

GBK 终端下日志与 stdout 无乱码字符；JSON.parse 后中文完整；带中文的 .ps1 在 PS 5.1 可执行。
