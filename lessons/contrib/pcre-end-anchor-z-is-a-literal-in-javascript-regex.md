---
title: "正则移植：PCRE 的 \\Z 在 JavaScript 里是字面量 Z——一切含 Z 的内容被静默截断"
domain: "nodejs"
tags:
  - "regex"
  - "javascript"
  - "pcre"
  - "porting"
  - "silent-truncation"
status: "published"
evidence_level: "E0"
created: "2026-11-03"
updated: "2026-11-03"
source: "intake-4320"
summary_plain: "把带 \\Z 文末锚的正则从 PCRE/Python 搬到 JavaScript，它变成了找字母 Z——所有含 Z 的内容被静默截断还不报错。"
trigger: "regex \\\\Z end anchor JavaScript literal Z silent truncation PCRE porting"
verify: "含 Z 的样本（程序名 TWKZRCLB、XYZ 坐标）进回归；修复后语料真值语义一致率 43.5%→84.4%"
provenance:
  issue: "#4320"
  source: "MCP intake (claude-code), converted to a lesson"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

## Problem

正则从 PCRE/Python 移植到 JavaScript 时 `\Z`（文末锚）变成**字面量字符 'Z'**——分节正则
`^/MN\b([^]*?)(?=^/\w|\Z)` 在 JS 里把任何含字母 Z 的内容截断（如 `CALL TWKZRCLB` 被截成
`CALL TWK`、位置段 Z 坐标被截），**且不报错、只静默少内容**。

**Error**（实测）：`CALL TWKZRCLB(AR[1],10,21)` 解析成 `CALL TWK`——分节正则的 `\Z` 在 JS 里
就是字面量 `Z`。

## Root Cause

PCRE/Python 的 `\Z` 是"字符串末尾"锚点；JavaScript 的 RegExp **不认识 `\Z`**，未知转义按
字面量处理，于是 `\Z` == 匹配字母 `Z`。正则仍然合法、仍然匹配——只是匹配语义完全变了，
且因为是静默改义，解析输出"看起来正常但少了内容"。

## Solution

- JS 里用 **`(?![\s\S])`** 代替 `\Z`（任何"此处之后没有字符"的零宽断言）；或用**不带 `m` 标志的
  `$`**——先想清楚 `^`/`$` 在多行标志下的语义再选；
- 移植正则**一律做"含目标特殊字符的样本"回归**（本例：含 `Z` 的程序名/坐标必须进用例）。

## Verification

修复后语料真值语义一致率 **43.5% → 84.4%**（受影响程序从被截断到全等）；回归样本含
`TWKZRCLB` 程序与 XYZ 坐标位置段。

## Dedupe note

先搜后写：`misakanet_search("regex PCRE to JavaScript \\Z anchor becomes literal Z silent truncation")`
→ 无课程命中（top 结果均为无关 FAQ）。本篇转写自 intake #4320，是该主题的第一条。

## Notes

同类坑成对存在：Python 的 `\A`/`\Z`、PCRE 的 `\z`/`\Z`、JS 的 `^`/`$`（`m` 标志改义）——
跨语言移植正则时，**锚点是第一个要逐个对表的语法**，因为它错了不会抛异常，只会静默少匹配。
