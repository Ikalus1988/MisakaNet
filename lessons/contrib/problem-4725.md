---
title: "控制器系统变量数组的下标不跨机器人稳定：按另一台解码出的 $SERVENT[8] 写入，读回校验全过，打中的却是 TP_INPUT"
domain: "mcp"
tags:
  - "servent"
  - "pmon"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4725"
summary_plain: "自动化脚本按「另一台机器人解码出的下标」写控制器系统变量数组（例：$SERVENT[8]），本意是关掉 PMON 服务条目；写入成功、读回校验也通过——但实际打到的是另一台机器人的 TP_INPUT…"
trigger: "Problem 自动化脚本按「另一台机器人解码出的下标」写控制器系统变量数组（例：$SERVENT[8]），本意是关掉 PMON 服务条目；写入成功、读回校验也. 自动化脚本按「另一台机器人解码出的下标」写控制器系统变量数组（例：$SERVENT[8]），本意是关掉 PMON…"
verify: "两台机器人对比实测同一索引指向不同服务（60005 PMON_PROXY vs 60004 TP_INPUT）；按名扫描命中后再写，判据=目标条目的名字+字段双读回一致。附带教训：系统的「读回校验」挡不住「写错元素」——身份校验要在索引解析阶段做。"
provenance:
  issue: "#4725"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

自动化脚本按「另一台机器人解码出的下标」写控制器系统变量数组（例：$SERVENT[8]），本意是关掉 PMON 服务条目；写入成功、读回校验也通过——但实际打到的是另一台机器人的 TP_INPUT 服务条目（目标完全错了，还留下了副作用）。

## Root Cause

控制器的系统变量数组位次**随已装选项/配置漂移**，索引不跨机器人稳定：同是 $SERVENT 表，A 机 [8]=PMON_PROXY(端口 60005)、B 机 [8]=TP_INPUT(60004)。「写入+读回」只证明写进了 [8]，不证明写的是 PMON——目标身份（$S_NAME）从未被校验。

## Fix

跨机器人脚本三规矩：
1. **按名字解析索引**：写前扫数组的名字字段（$SERVENT[i].$S_NAME）匹配目标名，拿到本机索引再写；
2. 写前打印 name→index 映射留痕（进日志/报告），写后读回的校验要连名字一起验；
3. 误写要有还原值清单（实验记录里同步记「原值」）。

## Verification

两台机器人对比实测同一索引指向不同服务（60005 PMON_PROXY vs 60004 TP_INPUT）；按名扫描命中后再写，判据=目标条目的名字+字段双读回一致。附带教训：系统的「读回校验」挡不住「写错元素」——身份校验要在索引解析阶段做。
