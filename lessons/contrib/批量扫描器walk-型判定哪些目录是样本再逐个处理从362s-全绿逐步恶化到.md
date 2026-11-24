---
title: "批量扫描器（walk 型：判定「哪些目录是样本」再逐个处理）从「362s 全绿」逐步恶化到 OOM 崩溃：Node 4GB 堆爆 → 提到 8G"
domain: "mcp"
tags:
  - "walk"
  - "oom"
  - "node"
status: "published"
evidence_level: "E1"
created: "2026-11-24"
updated: "2026-11-24"
source: "intake-5721"
summary_plain: "批量扫描器（walk 型：判定「哪些目录是样本」再逐个处理）从「362s 全绿」逐步恶化到 OOM 崩溃：Node 4GB 堆爆 → 提到 8GB 仍爆（exit 134，Mark-Compact allocation…"
trigger: "walk 扫描器 数据根顶层散件 根目录被当样本 整库读进内存 OOM sampling frame"
verify: "修复后同一语料：抽样 60 台 7.3s 全绿；全量 4067 样本 · 不符 0 · 299s · exit 0（修复前同规模 4GB/8GB 堆均崩）。注入判据：数据根顶层放任意 .ls，旧版必崩、新版照常（根不入样）。 根顶层放散件后全量扫描照常绿；单样本超上限时报读取失败而非 OOM；全量不符 0 exit 0。"
provenance:
  issue: "#5721"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

批量扫描器（walk 型：判定「哪些目录是样本」再逐个处理）从「362s 全绿」逐步恶化到 OOM 崩溃：Node 4GB 堆爆 → 提到 8GB 仍爆（exit 134，Mark-Compact allocation failure）。按「泄漏」和「堆上限」两个方向排查都对不上：单样本内存放大复现不了，模块级缓存也没有。

## Root Cause

扫描器把「含样本特征文件（如 .ls/.tp）的目录」判定为样本目录且不再下钻。语料库在日常整理中往**数据根顶层**散落了一个 .ls 文件——于是 2GB 的整棵语料树被判定为「一个样本目录」，被一口气全部读进内存。不是泄漏、不是堆上限，是**采样框 bug**：扫描根本身被当成了叶子样本。

## Fix

1. 数据根自身**永不参与**样本判定（只下钻找真样本目录）；
2. 单样本读取加总量上限（超出按读取失败计数上报，不硬吞）；
3. 排障工具沉淀：内存探针用文件落盘（appendFileSync）而不是 stdout——V8 FATAL abort 时管道缓冲全丢，探针打印会「一行都没打过」的假象。

## Verification

修复后同一语料：抽样 60 台 7.3s 全绿；全量 4067 样本 · 不符 0 · 299s · exit 0（修复前同规模 4GB/8GB 堆均崩）。注入判据：数据根顶层放任意 .ls，旧版必崩、新版照常（根不入样）。

根顶层放散件后全量扫描照常绿；单样本超上限时报读取失败而非 OOM；全量不符 0 exit 0。
