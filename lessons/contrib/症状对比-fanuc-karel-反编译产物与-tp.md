---
title: "症状：对比 FANUC KAREL 反编译产物与 TP 版实现的逻辑等价性时，反编译文本里两个 IF 出现「空 THEN 体」，一处 WAIT 丢失成 stra"
domain: "fanuc"
tags:
  - "fanuc"
  - "karel"
  - "tp"
status: "published"
evidence_level: "E1"
created: "2026-11-23"
updated: "2026-11-23"
source: "intake-5616"
summary_plain: "症状：对比 FANUC KAREL 反编译产物与 TP 版实现的逻辑等价性时，反编译文本里两个 IF 出现「空 THEN 体」，一处 WAIT 丢失成 stray 残影、一处循环条件渲染成…"
trigger: "反编译 空 IF 体 RET/RETURN 丢失 UNTIL(0<=5) ABS UNK 渲染缺口 语义对比误判"
verify: "对争议语句取 token 流：空 IF 体内出现 RET token（本案偏移 1904/2222）即证实丢失 RETURN；UNTIL 条件出现 UNK 80 + INT 5 + LE 即证实 ABS(x)<=5。复核后两版逻辑逐指令一致、仅剩调用契约与一处信号极性差异，判定可互换。 token 流复核：空 IF 体内见 RET token 即证实；UNK 80+INT+LE 即证实 ABS…"
provenance:
  issue: "#5616"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

症状：对比 FANUC KAREL 反编译产物与 TP 版实现的逻辑等价性时，反编译文本里两个 IF 出现「空 THEN 体」，一处 WAIT 丢失成 stray 残影、一处循环条件渲染成 UNTIL((0<=5))。按文本直读会得出「跳过语义不一致 / 死循环 / 等待条件丢失」三个假分歧，险些误判两版不可互换。

## Root Cause

pc2kl3 类反编译器的四个渲染缺口叠加：
1) IF 体尾的 RETURN(0) 语句丢失不渲染，只剩空 IF——真实语义是「条件成立则提前返回（跳过工艺）」，与对照方的跳转语义其实一致；
2) ABS 算子（0x50）未映射渲染成 UNK + 操作数兜底 0，|目标-实际|<=5 的等待条件变成 UNTIL((0<=5))；
3) PULSE 指令降级为赋值 + residue 注释，丢失脉宽；
4) WAIT 型语句整体丢失，只留被读变量的 stray 残影。
根因共性：反编译文本是「索引」不是「证据」，渲染缺口会系统性伪装成语义分歧。

## Fix

语义对比凡遇以下形态一律落字节码逐 token 复核后再下结论：① 空 IF 体（先查体内是否有丢失的 RET/RETURN）；② UNTIL/条件里出现常量比较（0<=5 之类，查 UNK 算子位——0x50=ABS、0x67=REAL ABS）；③ 赋值后跟 residue 数字（可能是 PULSE 时长或丢失的 WAIT 超时）；④ stray 残影处（被读变量+NOP+跳转 = WAIT 条件）。
复核工具：反编译器自带 tokenizer（scan）逐 token dump（offset+kind+payload），RET/ABS/WAIT 的真身一目了然。

## Verification

对争议语句取 token 流：空 IF 体内出现 RET token（本案偏移 1904/2222）即证实丢失 RETURN；UNTIL 条件出现 UNK 80 + INT 5 + LE 即证实 ABS(x)<=5。复核后两版逻辑逐指令一致、仅剩调用契约与一处信号极性差异，判定可互换。

token 流复核：空 IF 体内见 RET token 即证实；UNK 80+INT+LE 即证实 ABS 比较；复核后假分歧全部消除、结论可复现。
