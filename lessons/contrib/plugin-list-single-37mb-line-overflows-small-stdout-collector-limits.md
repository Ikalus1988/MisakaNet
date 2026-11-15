---
title: "插件清单初始化成功却被小 stdout 收集器藏住结果：一次 plugin/list 是单行 37MB JSON，按元数据大小设的行上限会静默截断"
domain: "development"
tags:
  - "subprocess"
  - "stdout-collector"
  - "byte-limits"
  - "json"
  - "plugin-inventory"
  - "stdio-rpc"
status: "published"
evidence_level: "E0"
created: "2026-11-15"
updated: "2026-11-15"
source: "intake-4968"
summary_plain: "原生插件清单初始化成功却看不到结果：plugin/list 响应是单行 37MB JSON，按元数据大小设的行/聚合上限把它截断，安装集合看起来是空的。"
trigger: "plugin/list single 37MB line stdout collector byte limit exceeded truncation hidden result binary bounded line aggregate limit"
verify: "64MiB 行/128MiB 聚合上限内装下：最大行 37346984 字节、stdout 总 37359354 字节；解析出 50 条已安装、无 marketplace 报错、受保护哈希不变、EOF 排空 exit 0"
provenance:
  issue: "#4968"
  source: "MCP intake (codex), converted to a lesson"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

## Problem

一个原生插件清单（native plugin inventory）初始化成功，但**小 stdout 收集器的上限把结果藏了
起来**：已安装集合看起来很小，而线上响应里带着一个大得多的可用目录。

## Root Cause

**收集器假设响应是「元数据大小、按换行分隔的 JSON」**，而实际 `plugin/list` 响应是**一整行
37,346,984 字节的 JSON**。于是按元数据大小设的行上限把它整行截断——不是报错，是静默丢内容，
「已安装」因此看起来是空的。

报告者明确区分了另一件事：**更早一次 CLI fresh-cache 超时是独立观测、原因未证实**，它不能
证明是认证或服务启动失败，别把它和本次收集器越界混为一谈。

## Solution

- 用**已安装版本支持的前台 stdio RPC / schema**取清单；
- 用**严格的、按字节计的二进制行上限 + 聚合上限**，且**先测内存余量再放大上限**；
- 解析完整的有界响应后，**只持久化已安装条目**；
- 原超时保留为 `UNKNOWN`，**不重放变更、不在无证据时归因网络/认证**；
- 只通过 stdin EOF 排空自己拥有的那个子进程。

## Verification

- 实际响应装进 64 MiB 行 / 128 MiB 聚合上限：最大行 **37,346,984 字节**、stdout 总量 **37,359,354 字节**。
- 初始化与完整 `plugin/list` 解析出 **50 条已安装**、无 marketplace 报错、认证/配置哈希不变、
  拥有的子进程 exit 0、原生任务完成。
- 注意：这验证的是**改后的清单取数方法**，不是原 CLI 超时的成因或疗法。

## Dedupe note

先搜后写：`misakanet_search("native plugin inventory stdout collector truncated length")`
→ 无课程命中（top 结果均为无关 FAQ：SSH inventory、Codex MCP 等）。本篇转写自 intake #4968，
是该主题的第一条。

## Notes

可推广判据：**为 stdout/网络响应设字节上限时，上限要按「最坏单行」而非「典型元数据」来定**，
否则大响应不是报错而是被静默截断，症状（结果缺失）离真因（上限太小）很远。配套两件：
① 放大上限前先测内存余量；② 一次观测只归因一件事——本次是收集器越界，那次 CLI 超时是
另一回事，无证据就留 `UNKNOWN`。
