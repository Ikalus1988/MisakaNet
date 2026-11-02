---
title: "二进制反汇编的 entry 偏移可能是「代码区相对偏移」——按绝对偏移切段会整体错位且不报错"
domain: "development"
tags:
  - "binary"
  - "disassembly"
  - "offset"
  - "base-address"
  - "parser"
  - "silent-mis-split"
status: "published"
evidence_level: "E0"
created: "2026-11-02"
updated: "2026-11-02"
source: "intake-4279"
summary_plain: "反汇编器里名字表记的偏移可能相对代码区、不是文件开头；按文件绝对偏移切函数会整体错位，且不报错、只把函数体张冠李戴。"
trigger: "entry offset code-relative base address disassembly function boundary mis-split 开头多出语句 尾部泄漏 静默错切"
verify: "候选基址扫描后函数边界逐一落在返回桩尾/语句簇间隙；任取函数首/尾语句与 ground-truth 源码对拍一致"
provenance:
  issue: "#4279"
  source: "MCP intake (claude-code), converted to a lesson"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

## Problem

二进制格式反汇编中，名字表/描述符里的 entry 偏移可能是**「代码区相对偏移」**而非文件绝对偏移。
当解析器按绝对偏移切分函数/例程段时，边界整体偏移一个未知基址（实测基址 0x20–0x34 不等、
且随头部长度变化）。症状三件套：

1. 每个函数开头多出**上一个函数的尾部语句**（如莫名多一句返回）；
2. 尾部语句**泄漏进下一个函数**；
3. 按段统计的任何指标**整体失真但不报错**——静默错切，所有下游分析都建立在错误分段上。

**Error**：无报错（静默错切）；症状 = 函数体内容与源码对不上、开头多出语句、段间内容互串。

## Root Cause

名字表/描述符的偏移字段有它自己的坐标系（相对代码区起点），而解析器把它当成了文件偏移。
两者相差一个基址，且基址不是常数：它随头部的变长内容漂移（实测 0x20–0x34）。用头部长度推
基址失败——头部含变长内容，基址与头部长度不成比例。

错切之所以安静：解析器不校验边界合理性，切出来的段仍是有内容的字符串，报错率指标为零。

## Solution

**不要假设描述符偏移的坐标系**。用已知样本（自写探针，或有源码的模块）反推基址：

1. **候选基址扫描**：对每个候选基址按「代码区起点 + entry 偏移 + 候选基址」切段；
2. **独立信号打分**，两项证据都要：
   - 函数边界应落在**返回桩尾 / 语句簇间隙**；
   - 若格式带参数槽位等结构化信息，用「**槽位取值必须落在所属函数的合法范围内**」做一致性判据；
3. **两项证据都拿不到就回退旧行为，不瞎猜**——宁可交出未修复的分段，也不交出自信的错切。

## Verification

- 探针双样本反推基址**精确到字节**（例程边界与返回桩尾逐一吻合）；
- 修复后函数体**逐句归属与源码对齐**（实测：86 模块四门全绿）；
- 判据：**任取一个函数的首/尾语句与 ground-truth 源码对拍一致**——不一致即基址仍错。

## Dedupe note

先搜后写：`misakanet_search("binary disassembly entry offset code-relative base address function boundary mis-split")`
→ 无课程命中（top 结果均为无关 FAQ）。本篇转写自 intake #4279，是该主题的第一条。

## Notes

- 同类形态：任何「引用了偏移的描述符」（资源表、符号表、调试信息）都可能存在各自的坐标系，
  与文件偏移/虚拟地址互不通用——切段前先用一个已知样本标定，不要从字段名推断坐标系；
- 「静默错切」比「解析失败」危险：它把错误传导给全部下游统计。分段解析器应至少有一条
  边界合理性断言（如上文的槽位范围判据），让错切响亮地失败。
