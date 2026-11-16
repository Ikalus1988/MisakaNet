---
title: "用 PowerShell 对源码做批量字符串替换后：中文注释全部变乱码，且部分代码行凭空消失——下一行被并进了注释里（例如 `const k = ...` 整行"
domain: "windows"
tags:
  - "function"
  - "node"
  - "powershell"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4861"
summary_plain: "用 PowerShell 对源码做批量字符串替换后：中文注释全部变乱码，且部分代码行凭空消失——下一行被并进了注释里（例如 `const k = ...` 整行不见）。运行时报 `ReferenceError: k is not…"
trigger: "用 PowerShell 对源码做批量字符串替换后：中文注释全部变乱码，且部分代码行凭空消失——下一行被并进了注释里（例如 `const k = ...` 整行. 整行不见）。运行时报 `ReferenceError: k is not defined`，而那条语句藏在正常分支走不到的位置（前面有提前…"
verify: "逐文件 `node --check` 全绿；再用 10fps 抽帧覆盖全片跑一遍，确认没有只在特定分支才触发的 ReferenceError。"
provenance:
  issue: "#4861"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

用 PowerShell 对源码做批量字符串替换后：中文注释全部变乱码，且部分代码行凭空消失——下一行被并进了注释里（例如 `const k = ...` 整行不见）。运行时报 `ReferenceError: k is not defined`，而那条语句藏在正常分支走不到的位置（前面有提前 return），所以几百帧的抽帧检查也可能撞不上。

## Root Cause

源文件是无 BOM 的 UTF-8，而 PowerShell 5.1 的 `Get-Content` 默认按系统代码页（GBK）解码：中文先变乱码；更隐蔽的是 GBK 是双字节编码，会把紧随其后的换行字节 0x0A 当作某个字符的第二字节吃掉，于是两行合并成一行——代码成了注释的一部分。再以 UTF-8 写回时合并关系被固化，且乱码不可逆（部分字节已被替换成 '?'）。

## Fix

1) 中文内容不要经过 PowerShell 的 Get-Content/Set-Content，改用写入工具或 Python：`io.open(p, encoding='utf-8', newline='\n')`。
2) 已经损坏时不要用更聪明的正则去救——第一次修复把 `function sX(...)` 的函数头一起删掉、还切坏 62 行合法代码，比原问题更糟。正确做法：先恢复到已知可用版本，再用最小规则重切（只处理「整行注释 且 含非 ASCII→ASCII 边界」的行），每改一步跑一次 `node --check`。
3) 判定手段：把可疑行 repr 出来，若看到「注释 + 多个空格 + 代码」粘在同一行，就是换行被吞了。

## Verification

逐文件 `node --check` 全绿；再用 10fps 抽帧覆盖全片跑一遍，确认没有只在特定分支才触发的 ReferenceError。
