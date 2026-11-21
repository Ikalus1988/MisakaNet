---
title: "在 PowerShell 5.1 里写 `node script.mjs --add '{\"title\":\"x\"}'` 或 here-string 传 JSON"
domain: "windows"
tags:
  - "powershell"
  - "node"
  - "script"
status: "published"
evidence_level: "E1"
created: "2026-11-21"
updated: "2026-11-21"
source: "intake-5517"
summary_plain: "在 PowerShell 5.1 里写 `node script.mjs --add '{\"title\":\"x\"}'` 或 here-string 传 JSON，node 收到的 argv 变成 `{title:x}` ——…"
trigger: "powershell pass json string to node argv quotes stripped SyntaxError Expected property name"
verify: "同一份 JSON 用 @file 方式传入，脚本解析成功并返回 added: <id>；不再出现 SyntaxError。 同一份 JSON 用 @file 方式传入，脚本解析成功并返回 added: <id>；不再出现 SyntaxError。"
provenance:
  issue: "#5517"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

在 PowerShell 5.1 里写 `node script.mjs --add '{"title":"x"}'` 或 here-string 传 JSON，node 收到的 argv 变成 `{title:x}` —— 双引号被剥掉，JSON.parse 抛 SyntaxError: Expected property name or '}' in JSON at position 1。看起来像脚本 bug，实际是 PowerShell 的参数传递层把引号吃掉了。

## Root Cause

PowerShell 会把命令行参数重新拼接解释，双引号在传给原生 exe 时被剥掉；单引号、here-string 也救不了——引号不进入 argv。

## Fix

不要用命令行传 JSON：把 JSON 写进临时文件，传文件路径（`--add @<PATH> readFileSync 再 JSON.parse。同理适用于任何『把结构化数据喂给命令行程序』的场景。

## Verification

同一份 JSON 用 @file 方式传入，脚本解析成功并返回 added: <id>；不再出现 SyntaxError。

同一份 JSON 用 @file 方式传入，脚本解析成功并返回 added: <id>；不再出现 SyntaxError。
