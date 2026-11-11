---
title: "UI 验收脚本一夜 13 条断言全红：不是回归，是测试数据被换了"
domain: "mcp"
tags:
  - "problem"
  - "ui"
  - "ro"
status: "published"
evidence_level: "E1"
created: "2026-11-11"
updated: "2026-11-11"
source: "intake-4659"
summary_plain: "UI 验收脚本一夜 13 条断言全红：不是回归，是测试数据被换了"
trigger: "UI 验收脚本一夜 13 条断言全红：不是回归，是测试数据被换了"
verify: "同一脚本复跑：41 通过 / 3 失败 = 文档基线（3 红为已知的原生对话框自动化缺口，非产品问题）；独立探针实测 release 产物页面文本含当前版本标签，证伪「版本断言是产品问题」的假设。"
provenance:
  issue: "#4659"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

桌面应用的 UI 验收脚本一夜之间 **13 条断言全红**（版本显示、系统变量组、变化点数量、时间线统计……），看起来像功能大面积回归。

## Root Cause

验收脚本的产物选择逻辑是「**debug 构建存在就优先用 debug**」——构建目录里躺着三周前的 debug 产物（旧版本号），脚本一直拿旧构建开测：版本断言比对的是 package.json 当前版本自然红，下游依赖导入流程的断言连锁红。产品源码与功能无辜。与「伴生资源污染验收环境」同族但机制不同：这次是**产物选择偏好**让陈旧构建长期遮住新构建。

## Fix

①产物选择改「release 优先、缺失才回退 debug」（与同库其它验收脚本同口径）；②起跑打印产物**路径 + mtime**——把「未生效先查产物」这条纪律工具化，旧构建一眼可辨。

## Verification

同一脚本复跑：41 通过 / 3 失败 = 文档基线（3 红为已知的原生对话框自动化缺口，非产品问题）；独立探针实测 release 产物页面文本含当前版本标签，证伪「版本断言是产品问题」的假设。
