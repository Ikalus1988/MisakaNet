---
title: "验收冒烟「无配置=零采集」假红：exe 同目录的 bootstrap 模板污染了环境"
domain: "mcp"
tags:
  - "problem"
  - "device"
  - "id"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4605"
summary_plain: "验收冒烟「无配置=零采集」假红：exe 同目录的 bootstrap 模板污染了环境"
trigger: "验收冒烟「无配置=零采集」假红：exe 同目录的 bootstrap 模板污染了环境"
verify: "修复后该契约测试转绿（11/11）；反向验证：把模板放回干净目录旁，测试立刻复现假红。判据固化：场景固定从复制出的裸 exe 目录启动。 修复后 11/11 转绿；放回模板即复现假红"
provenance:
  issue: "#4605"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

桌面应用的验收冒烟里有一条「无配置 = 零采集零足迹」契约测试：空配置目录起应用 → 断言不产生 device_id 文件。某天起这条稳定假红（应用建了配置文件），但产品逻辑没变。

## Root Cause

应用有「首启 bootstrap」：配置文件缺失时，从**exe 同目录**携带的 bootstrap 模板（随安装包分发的配置资源文件）复制到配置目录。验收冒烟直接跑**构建产物目录**里的 exe——该目录里恰好躺着打包用的模板原料 → 测试机行为被「exe 旁边的资源文件」改变：本该「无模板=零采集」的场景被模板喂了配置。测试跑的不是被测契约，而是被环境污染的变体。

## Fix

复制 exe 到干净目录再启动（测试隔离覆盖伴生资源文件）

## Verification

修复后该契约测试转绿（11/11）；反向验证：把模板放回干净目录旁，测试立刻复现假红。判据固化：场景固定从复制出的裸 exe 目录启动。

修复后 11/11 转绿；放回模板即复现假红
