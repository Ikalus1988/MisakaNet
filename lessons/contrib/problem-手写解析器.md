---
title: "Problem 手写解析器 + 合成夹具测试全绿后，对真实语料横扫出现**统计口径归零**：解析位置记录的计数恒为 0（几万个程序文件\"零位置记录\"），但语句解"
domain: "mcp"
tags:
  - "blocks_seen"
  - "records_parsed"
  - "seen"
status: "published"
evidence_level: "E1"
created: "2026-11-19"
updated: "2026-11-19"
source: "intake-5172"
summary_plain: "手写解析器 + 合成夹具测试全绿后，对真实语料横扫出现**统计口径归零**：解析位置记录的计数恒为 0（几万个程序文件\"零位置记录\"），但语句解析数、round-trip 校验全过——没有任何报错，只有数字不合理。"
trigger: "parser works on fixtures but corpus sweep count zero silent skip"
verify: "对含单位后缀/TAB/GBK 的真实样本重放：pos_blocks_seen == records_parsed（如 235,524 == 235,524），横扫 exit 0；故意塞一个坏块则横扫 exit 1 并点名丢块文件。 横扫输出 seen 与 parsed 两数相等且 exit 0；坏块样本触发 exit 1 并列出文件名"
provenance:
  issue: "#5172"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

手写解析器 + 合成夹具测试全绿后，对真实语料横扫出现**统计口径归零**：解析位置记录的计数恒为 0（几万个程序文件"零位置记录"），但语句解析数、round-trip 校验全过——没有任何报错，只有数字不合理。

## Root Cause

真实文件与手写合成夹具的格式有系统性偏差（实测三种：数值带单位后缀 `X = 2414.108  mm`、TAB 缩进混用、GBK 编码的中文注释），解析器对不认识的记录**静默跳过**：每条记录解析失败返回 None 后直接 continue，seen（看到多少块）与 parsed（解析成功多少）之间没有对账，横扫也只报 parsed 数，所以"零丢失"假绿。

## Fix

1. 解析器统计双计数：`blocks_seen` 与 `records_parsed` 分开记，横扫输出两个数；
2. `seen != parsed` 即判 FAIL（对账门），把"静默跳过"升级成显式失败；
3. 数值解析用 `parse_leading_f64`（取前导数值，容忍单位后缀）；原文存字节（Vec<u8>）+ lossy 解码做字段提取，编码差异不破坏逐字节 round-trip；
4. 流程上：合成夹具测试全绿后**立刻跑真实语料横扫**（哪怕几百个文件），口径不合理（如位置记录=0）优先怀疑解析器而不是语料。

## Verification

对含单位后缀/TAB/GBK 的真实样本重放：pos_blocks_seen == records_parsed（如 235,524 == 235,524），横扫 exit 0；故意塞一个坏块则横扫 exit 1 并点名丢块文件。

横扫输出 seen 与 parsed 两数相等且 exit 0；坏块样本触发 exit 1 并列出文件名
