---
title: "编译字节码（.pc/嵌入式 P-code 类）反汇编输出不可读：大段 .byte 噪音 + 操作数误读（把 1 字节 opcode 误读成「opcode+u8"
domain: "fanuc"
tags:
  - "pc"
  - "code"
  - "byte"
status: "published"
evidence_level: "E1"
created: "2026-11-02"
updated: "2026-11-02"
source: "intake-4029"
summary_plain: "编译字节码（.pc/嵌入式 P-code 类）反汇编输出不可读：大段 .byte 噪音 + 操作数误读（把 1 字节 opcode 误读成「opcode+u8 寄存器号」）。"
trigger: "编译字节码（.pc/嵌入式 P-code 类）反汇编输出不可读：大段 .byte 噪音 + 操作数误读（把 1 字节 opcode 误读成「opcode+u8. 编译字节码（.pc/嵌入式 P-code 类）反汇编输出不可读：大段 .byte 噪音 + 操作数误读（把 1 字节 opcode…"
verify: "消息模板与报警原文逐字吻合；短串/长串全量收齐（串库 113 条，8 个消息出口全卡片化）；名字表关键信号与 summary.dg 机架段原文一致"
provenance:
  issue: "#4029"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

编译字节码（.pc/嵌入式 P-code 类）反汇编输出不可读：大段 .byte 噪音 + 操作数误读（把 1 字节 opcode 误读成「opcode+u8 寄存器号」）。

## Root Cause

根因与修复（可复现方法论）：①opcode/operand 宽度有歧义时必须双证定夺——(a) 源码↔编译件罗塞塔对照（同一字符串常量在编译件里的字节形态可直接定 encoding：串推送=3f<len><bytes>，若把其前的 0x27 与 0x3f 读成寄存器操作数则串将失去 opcode）；

## Fix

罗塞塔定 encoding（3f/2e/aa/7d/31 00 4f/3e 锚点）+ 后继分布定 operand 宽度（27=1 字节 op）；消息卡串链折叠 + 串库分族 + 符号表 + 短串上下文收认；表格逐行解析

## Verification

消息模板与报警原文逐字吻合；短串/长串全量收齐（串库 113 条，8 个消息出口全卡片化）；名字表关键信号与 summary.dg 机架段原文一致
