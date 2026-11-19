---
title: "症状 一个板间链路审查工具有两条互相冲突的要求： - 从 STM32CubeMX 的 .ioc 抽出 13 条板间链路（同名外设 + TX↔RX 引脚交叉，可信"
domain: "dsh"
tags:
  - "if"
  - "stm32cubemx"
  - "ioc"
status: "published"
evidence_level: "E1"
created: "2026-11-19"
updated: "2026-11-19"
source: "intake-5233"
summary_plain: "一个板间链路审查工具有两条互相冲突的要求： - 从 STM32CubeMX 的 .ioc 抽出 13 条板间链路（同名外设 + TX↔RX 引脚交叉，可信度高）； - 纪律要求「推断的结论不能判人…"
trigger: "inferred 推断结果 不落地 死胡同 only_allow_declared 闸门没有出口 promote 人工确认"
verify: "四步闭环，均有实测： 1. 闸门生效：only_declared=True 时 apply_draft 返回 0，design.links_list 仍为空。 2. 显式确认后写入：promote(draft, ids) 把选定链路标成 declared 并记 promoted_from=inferred；再 apply_draft 返回 13。 3…"
provenance:
  issue: "#5233"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

一个板间链路审查工具有两条互相冲突的要求：
- 从 STM32CubeMX 的 .ioc 抽出 13 条板间链路（同名外设 + TX↔RX 引脚交叉，可信度高）；
- 纪律要求「推断的结论不能判人 fail」——如果推断错了却让设计报错，人会开始怀疑检查器而不是自己的设计。

第一版两边都做了，结果进入死胡同：13 条链路全部标 source=inferred，落地函数 apply_draft(only_declared=True) 一条都不写。于是：

- 抽出的链路写不进设计（links_list 仍为空）；
- 链路检查仍返回 status=not_ready, declared_links=0；
- 用户看到的报告和「根本没做抽取」时一模一样。

同样的错在另一处也发生了：断言层从网表推出「R1 是 3.3V 到 PB10 的上拉」，但断言生成函数只产出一条 claim.R1.connected。删掉 R1 时系统只是少一条断言（变安静），没有一条断言说「PB10 悬空了」（变红）。

## Root Cause

「不许用推断做硬判定」这条纪律被实现成了纯闸门，没有配套的确认通道。

纪律本身是对的（推断会错），但它只规定了「不能自动生效」，没规定「那要怎样才生效」。缺了后者，严格执行纪律的结果就是功能完全不可用 —— 而不可用在界面上和「没实现」无法区分。

更深一层：这类闸门容易写成 if ... continue 一行，看起来优雅、测试也容易过（断言不写就是通过），但**没有任何测试会失败**，因为「什么都没发生」正是期望的结果。这是一个自我验证的假象。

## Fix

1. 推断结论带 source 字段（declared / inferred / measured），硬检查一律 `if source == "inferred": continue`，只提示不判 fail。
2. 推断结果默认不落地。apply 只写 declared，要落地必须显式 promote（人工逐条或批量确认），promote 后记 promoted_from 以便追溯。
3. 必须有出口：只有闸门没有确认通道 = 抽出来的结果永远用不上。提供 review_list()（按可信度排序 + 证据 + 待办动作）和 promote(ids) 两个函数。
4. 回归双侧：去掉闸门要立刻红（断言 added==0），promote 后要能写入（断言 added>0 且 validate 真的检查了）。

## Verification

四步闭环，均有实测：
1. 闸门生效：only_declared=True 时 apply_draft 返回 0，design.links_list 仍为空。
2. 显式确认后写入：promote(draft, ids) 把选定链路标成 declared 并记 promoted_from=inferred；再 apply_draft 返回 13。
3. 检查真的执行：links.validate 的 checked.declared_links 从 0 变成 13，status 从 not_ready 变成 ok。
4. 退化验证：去掉闸门（让 inferred 也直接落地），第 1 条立刻 FAIL（实测 added=13）；恢复后 PASS。同时断言 promote 之前不可能有 declared 链路。
