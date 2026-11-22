---
title: "用编辑工具改一份原本带 UTF-8 BOM 的 .ps1（中文注释 + 中文提示），改完一跑就报一串 `Unexpected token '}' in expr"
domain: "windows"
tags:
  - "utf"
  - "bom"
  - "ps1"
status: "published"
evidence_level: "E1"
created: "2026-11-22"
updated: "2026-11-22"
source: "intake-5554"
summary_plain: "用编辑工具改一份原本带 UTF-8 BOM 的 .ps1（中文注释 + 中文提示），改完一跑就报一串 `Unexpected token '}' in expression or statement` / `The Try…"
trigger: "powershell script Unexpected token '}' Try statement missing Catch parse error after edit BOM removed 中文乱码 ps1"
verify: "① 文件头三字节为 239,187,191；② `powershell -NoProfile -ExecutionPolicy Bypass -File <脚本>` 退出码为 0，且输出里中文显示正常（不再出现「鏉」「闂」等乱码字符）。 ① 文件头三字节为 239,187,191；② `powershell -NoProfile -ExecutionPolicy Bypass -File…"
provenance:
  issue: "#5554"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

用编辑工具改一份原本带 UTF-8 BOM 的 .ps1（中文注释 + 中文提示），改完一跑就报一串 `Unexpected token '}' in expression or statement` / `The Try statement is missing its Catch or Finally block`，报错处显示的源码是乱码（如「鏉?路 闂」）。脚本本身逻辑没动，只是多了一个检查块。

## Root Cause

① 编辑写入时丢掉了文件头的 BOM（EF BB BF）；② Windows PowerShell 5.1 读「无 BOM 的 .ps1」按系统代码页（GBK/936）解码，UTF-8 的中文被解错，行尾的中文引号把后面的 `}` 一起吞掉，于是语法崩；③ 若脚本被「后台异步调用」（如 HTTP 处理里 execFile 后立刻返回），这次崩溃不会有任何回执，表现为功能静默失效。

## Fix

① 编辑任何含中文的 .ps1 后，检查文件头是否仍是 EF BB BF：`[System.IO.File]::ReadAllBytes($p)[0..2]` 应为 239,187,191；② 丢了就写回：`[System.IO.File]::WriteAllBytes($p, ([byte[]](0xEF,0xBB,0xBF)) + [System.IO.File]::ReadAllBytes($p))`；③ 更稳：一律用 `[System.IO.File]::ReadAllText/WriteAllText + New-Object System.Text.UTF8Encoding($true)` 读写；④ 改完必须真跑一次并检查退出码，不能只看编辑成功。

## Verification

① 文件头三字节为 239,187,191；② `powershell -NoProfile -ExecutionPolicy Bypass -File <脚本>` 退出码为 0，且输出里中文显示正常（不再出现「鏉」「闂」等乱码字符）。

① 文件头三字节为 239,187,191；② `powershell -NoProfile -ExecutionPolicy Bypass -File <脚本>` 退出码为 0，且输出里中文显示正常（不再出现「鏉」「闂」等乱码字符）。
