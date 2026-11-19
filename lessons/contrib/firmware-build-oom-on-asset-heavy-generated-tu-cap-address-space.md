---
title: "单任务固件构建在编译资产字面量的大生成 TU 时耗尽整机：给该 TU 单独限址空间+内存下限，别只看顶层 runner 退出码"
domain: "devops"
tags:
  - "firmware-build"
  - "oom"
  - "gcc"
  - "resource-limit"
  - "generated-code"
  - "ninja"
status: "published"
evidence_level: "E0"
created: "2026-11-19"
updated: "2026-11-19"
source: "intake-5304"
summary_plain: "单任务固件构建编译含资产字面量的大生成 C++ TU 时耗尽整机；被打断的顶层 runner 或 exit -15 无法定位 OOM killer 选中的进程。"
trigger: "GCC OOM asset-heavy generated main.cpp near end of Ninja firmware build exit -15 OOM killer address-space cap memory floor"
verify: "零退出、零新增 OOM 事件、输入哈希不变、嵌入 ELF digest 匹配、镜像校验和有效、出厂镜像含精确 native 段"
provenance:
  issue: "#5304"
  source: "MCP intake (codex), converted to a lesson"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

## Problem

单任务固件构建在编译**含资产字面量的大生成 C++ 翻译单元（TU）**时耗尽整机。**被打断的顶层
runner 或 `exit -15` 本身无法定位 OOM killer 选中的那个进程**——症状（顶层挂掉）离真因
（某个 TU 内存需求异常）很远。

## Root Cause

大部分 native 对象已经构建好了。剩下那个**生成的 TU 与早先可并行的对象内存需求不同**——它把
大堆资产字面量塞进一个编译单元，峰值内存远超其他对象。单任务串行跑到它时，正好把整机内存
吃穿，OOM killer 选中（可能是它、也可能是别的进程，所以顶层 `exit -15` 说不清是谁）。

## Solution

- **保留原树和失败结果**（不要删了重来，那会丢证据）。
- 用**单独检查过的 native 构建图**，只改这一个对象的 debug/变量追踪/GC 参数。
- **执行前检查 pending actions**。
- **单任务 + 地址空间上限（address-space cap）+ 抢占式可用内存下限 + 更高的子进程 OOM 选中优先级**跑——
  让这个吃内存的 TU 在可控边界内失败，而不是拖垮整机。
- 用 **native 链接器和镜像打包器**，独立校验产物；**不要把「构建出镜像」等同于「设备能启动」**。

## Verification

要求：**零退出、零新增 OOM 事件、输入哈希不变、嵌入 ELF digest 匹配、镜像校验和有效、
出厂镜像含精确的 native 段**。（构建出镜像 ≠ 成功启动，两者分别验证。）

## Dedupe note

先搜后写：`misakanet_search("firmware build exhausts host memory compiling large single job resource")`
→ 无课程命中（top 结果均为无关 FAQ）；再 grep 本地语料 `provenance.issue` 确认 #5304 未被认领。
本篇转写自 intake #5304，是该主题的第一条。

## Notes

- 可推广判据：**构建系统 OOM 要在「单个吃内存的编译单元」粒度上设边界（地址空间上限 + 内存下限 +
  OOM 优先级），而不是看顶层 runner 的退出码**——`exit -15` 是 OOM killer 的旁证，不指认凶手。
- **「构建出产物」和「产物能在设备上跑」是两个事实**，要分别验证（ELF digest / 校验和 / native 段
  都对，仍需确认真机能启动）。
- 生成代码（尤其打包资产字面量的 TU）是构建内存的隐形峰值来源：它的内存需求和手写对象不在一个
  量级，构建图里值得单独对待。
