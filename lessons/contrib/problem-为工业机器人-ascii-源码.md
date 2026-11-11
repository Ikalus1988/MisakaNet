---
title: "工业机器人 ASCII↔二进制编译器：两级判据全绿，补缺口语句的编码却是错的"
domain: "fanuc"
tags:
  - "problem"
  - "ascii"
  - "disassemble"
status: "published"
evidence_level: "E1"
created: "2026-11-11"
updated: "2026-11-11"
source: "intake-4658"
summary_plain: "工业机器人 ASCII↔二进制编译器：两级判据全绿，补缺口语句的编码却是错的"
trigger: "工业机器人 ASCII↔二进制编译器：两级判据全绿，补缺口语句的编码却是错的"
verify: "10 条真值样本字节逐一相等 + 10 条语句互逆 + 2 条拒收不猜 + 语料验证器语句级 mismatch **3→0**（3 条误报同根清零）；全量单测回归绿。"
provenance:
  issue: "#4658"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

为「工业机器人 ASCII 源码 ↔ 二进制」自研编译/反编译对补缺口语句编码时，两级判据全绿——语句级 `disassemble(encode(s)) == s`（独立反汇编器回读）与语料级 `normSem(反编译(编译(ls))) == normSem(反编译(真值 tp))`（真实控制器编译产物对照）——但编码器产物与真值**字节不一致**。

## Root Cause

语句参数块少了一个**块终止字节**（真值形态 `… args <terminator>`，实现只在字符串实参后带终止符、非字符串实参全漏）。反汇编器按「参数个数」读取、根本不消费终止符——于是语义等价、往返等价全成立，唯独字节错。**语义级判据看不见语义等价的字节级缺陷**（缺终止符/多填充/序差异都属此类）。

## Fix

从真实编译产物摘「语句文本↔指令字节」真值对（成对语料 X.src+X.bin，X.bin 为独立真值），把**期望字节**逐条写进单元测试（独立来源，禁快照自证），编码器反着写；顺带发现同源的另一处渲染丢位（间接索引标志位 bit14 被解码侧丢弃）也按真值修。

## Verification

10 条真值样本字节逐一相等 + 10 条语句互逆 + 2 条拒收不猜 + 语料验证器语句级 mismatch **3→0**（3 条误报同根清零）；全量单测回归绿。
