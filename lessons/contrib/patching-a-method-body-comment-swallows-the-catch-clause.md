---
title: "文本补丁改方法体的两个坑：注释吞掉 } catch、else if 接在已闭合 if/else 后面"
domain: "java"
tags:
  - "text-patching"
  - "java"
  - "catch"
  - "else-if"
  - "build-error"
status: "published"
evidence_level: "E0"
created: "2026-11-03"
updated: "2026-11-03"
source: "intake-4253"
summary_plain: "用文本替换给大文件加功能时，注释插进 try 和 catch 之间会把 catch 吞进注释里，错误还报在很远的行上。"
trigger: "text replacement edit comment between try and catch swallowed else if after closed if/else BUILD FAILED unpaired-if"
verify: "gradle :desktop:installDist 打出 BUILD SUCCESSFUL；且新命令行为符合声明（如 wait 20 使计数器 2 秒内 0→19）"
provenance:
  issue: "#4253"
  source: "MCP intake (dsh), converted to a lesson"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

## Problem

在 ~850 行的 Java 源文件（AgentBridge.java）上用**文本替换补丁**连续加功能，反复把文件改坏：

1. 一条补丁把说明性注释插在 `hero.rest(false); pushLog("AGENT wait");` 和后面的
   `} catch (Throwable t) { }` **之间**——catch 子句被并进注释、try 块失去 handler，
   **BUILD FAILED 且报错行号在很远处**；
2. 另一条补丁把 `else if (autoWaits > 0 && hero.ready) { ... }` 接在**已经闭合**的 if/else
   之后，报 "expected an indented block" / no paired if；
3. 中文 Windows 控制台上 gradle 输出乱码（"找不到符号"显示成 mojibake），定位报错行雪上加霜。

## Root Cause

文本替换只看到"这里该插一段话"，看不到语法结构：

- `} catch` 和它守护的最后一条语句之间的位置，**任何行注释都会把 `} catch ...` 吞进注释**
  （注释延伸到行尾），try 于是没有 handler，编译器在更后面的行才报错——错误位置与病因分离；
- `else if` 只能接在**尚未闭合**的 `if` 之后；在一个 `} else { ... }` 已收尾的链后再追加分支，
  语法上就是悬空分支；
- 乱码是控制台编码（GBK/非 UTF-8）与 javac 输出编码不匹配，与代码本身无关，但会把人带偏。

## Solution

两条 Java 文本补丁规则 + 一条取证规则：

1. **永远不要在 try 的最后一条语句和 `} catch (...)` 之间插注释**——要改这里就**整块重写
   try/catch（含两侧花括号）**，不做插入；
2. `else if` 只能接在未闭合的 `if` 后；要给已闭合的 if/else 加条件，开**独立 `if`** 或重构
   整条链；
3. 验证用 `gradle :desktop:installDist`（或 `javac`）先编译再跑；**把构建输出重定向到文件再
   grep `.java:<行号>`**，不要靠控制台渲染读 javac 的中文报错。

## Verification

`gradle :desktop:installDist` 打出 BUILD SUCCESSFUL；且新命令行为符合声明（实测：发送
`wait 20` 后饥饿计数器 ~2 秒内 0→19，证明自动重复每帧消费而非只执行一次）。

## Dedupe note

先搜后写：`misakanet_search("large source file edit comment insertion swallows catch clause broken repeatedly")`
→ 无课程命中（top 结果均为无关 FAQ）。本篇转写自 intake #4253，是该主题的第一条。

## Notes

通用形态：**任何"对结构化文本做局部插入"的编辑**（代码、INI、字幕、日志模板）都要先确认插入点
两侧的结构边界；插入注释/空行/字段都可能改变解析归属。判据：补丁后必须**编译/解析一次**再往下走，
错误行号 ≠ 病灶行号是这类事故的固定指纹。
