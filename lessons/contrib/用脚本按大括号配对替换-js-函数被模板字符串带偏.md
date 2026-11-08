---
title: "用脚本按大括号配对替换 JS 函数：模板字符串里的 ${} 会把配对带偏，整份文件被截断"
domain: "devops"
tags:
  - "javascript"
  - "refactor"
  - "brace-matching"
  - "template-literal"
  - "file-corruption"
status: "published"
evidence_level: "E1"
created: "2026-11-08"
updated: "2026-11-08"
source: "intake-4554"
summary_plain: "用一段\"找到函数起点、从起点数大括号到配对为止、把这段整体替换\"的脚本去改一个 JS 模块（sceneKit.js 里替换 doorway/mirror 两个函数）。脚本跑完报成功、文件大小也变了，但页面直接白屏。node 解析时报…"
trigger: "用脚本按大括号配对替换 JS 函数：模板字符串里的 ${} 会把配对带偏，整份文件被截断. 用一段\"找到函数起点、从起点数大括号到配对为止、把这段整体替换\"的脚本去改一个 JS 模块（sceneKit.js 里替换 doorway/mirror…"
verify: "替换后立即 `node -e \"import('<PATH>').then(...).catch(e=>console.log(e.message))\"` 做一次语法加载检查；再渲染一帧对比。两条都过才算改成功——只看到脚本打印\"已替换\"不算。"
provenance:
  issue: "#4554"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

用一段"找到函数起点、从起点数大括号到配对为止、把这段整体替换"的脚本去改一个 JS 模块（sceneKit.js 里替换 doorway/mirror 两个函数）。脚本跑完报成功、文件大小也变了，但页面直接白屏。node 解析时报 `Unexpected token '="`，检查发现文件后半截被切掉：新函数之后残留了一段旧函数体。

## Root Cause

配对逻辑只数 `{` 和 `}` 的字面数量，不区分字符串、模板字符串和注释。该文件里大量出现 `` `${expr}` `` 和模板字符串中的花括号，这些 `}` 让计数提前归零，切割点落在函数中间，于是起点到切割点之间的内容被新文本替换，切割点之后的旧内容残留，整个模块语法失效。

## Fix

改法有二，按代价从低到高：1）这类文件不要用脚本做函数级替换，直接整份重写（写工具覆盖全文件，最稳）；2）必须脚本化时，先剥掉字符串/模板字符串/注释再计数，或直接用 AST 工具（acorn/babel parse 后按节点 range 替换）。判断准则：文件里只要出现模板字符串或含花括号的字符串，括号计数法就不可用。

## Verification

替换后立即 `node -e "import('<PATH>').then(...).catch(e=>console.log(e.message))"` 做一次语法加载检查；再渲染一帧对比。两条都过才算改成功——只看到脚本打印"已替换"不算。
