---
title: "cordis patch 的 !!js 表达式里 Windows 反斜杠会被 JS 吃掉"
domain: "devops"
tags:
  - "dsh"
  - "cordis"
  - "yaml"
  - "js-expression"
  - "windows-path"
  - "backslash"
status: "published"
evidence_level: "E1"
created: "2026-11-02"
updated: "2026-11-02"
source: "intake-4248"
summary_plain: "在 DSH 的 cordis.patch.yml 里用 !!js 表达式拼 Windows 路径（如 <PATH>\\Users\\\\x\\\\.dsh\\\\bin\\\\x.mjs），插件启动时报文件不存在，实际拼出来的路径里夹着奇怪字符。"
trigger: "cordis patch 的 !!js 表达式里 Windows 反斜杠会被 JS 吃掉. 在 DSH 的 cordis.patch.yml 里用 !!js 表达式拼 Windows 路径（如…"
verify: "打印实际拼出来的路径，与真实文件路径一致，插件能加载。"
provenance:
  issue: "#4248"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

在 DSH 的 cordis.patch.yml 里用 !!js 表达式拼 Windows 路径（如 <PATH>\Users\\x\\.dsh\\bin\\x.mjs），插件启动时报文件不存在，实际拼出来的路径里夹着奇怪字符。

## Root Cause

YAML 单引号标量里反斜杠是字面量，但该标量随后被当 JavaScript 源码求值——JS 字符串里的 \\p、\\r、\\b 被解释成控制字符（\\r 回车、\\b 退格），路径被破坏。

## Fix

在 !!js 表达式内部只用正斜杠（Windows 同样接受），或者把反斜杠写成双反斜杠；路径拼装优先用环境变量 + 正斜杠。

## Verification

打印实际拼出来的路径，与真实文件路径一致，插件能加载。
