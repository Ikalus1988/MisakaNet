---
title: "dsh-mnemon 新增记忆空间后全部空间消失：Provider 字段 scope 用错导致整批 body 加载中断"
domain: "mcp"
tags:
  - "dsh"
  - "dsh-mnemon"
  - "memory-space"
  - "provider-config"
status: "published"
evidence_level: "E1"
created: "2026-11-11"
updated: "2026-11-11"
source: "intake-4673"
summary_plain: "在 DSH 的 dsh-mnemon 里给记忆空间注册表（state/memory-providers.json，version 4：services/enabled/bodies）新增第二个 Provider…"
trigger: "dsh-mnemon 新增记忆空间后全部空间消失：Provider 字段 scope 用错导致整批 body 加载中断. 在 DSH 的 dsh-mnemon 里给记忆空间注册表（state/memory-providers.json，version…"
verify: "改回正确 scope 并重载后 memorySpaces.total 从 0 回到 2（openviking + holographic），两个 Provider status 均 healthy，写入与召回各验证一次成功；对照实验把 dataPath 放回 body.connection 立即复现 total=0。"
provenance:
  issue: "#4673"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

在 DSH 的 dsh-mnemon 里给记忆空间注册表（state/memory-providers.json，version 4：services/enabled/bodies）新增第二个 Provider 空间后重载插件，原本健康的记忆空间全部消失：mnemon_status 返回 memorySpaces.total=0、providers 只剩一个 idle 项，无任何报错，注册表文件本身完好（两个 body 都在）。

## Root Cause

Provider 字段带 scope（service 级 vs memory 级）。把 service 级字段 dataPath 写进 body.connection 后该 body 校验抛错，整个 bodies 数组的加载/reconcile 中断，于是连原本合法的空间一起没登记，表现为 total=0 而不是只丢新增那个。附带错误：dataPath 期望 store.json 文件路径，给成目录同样失败。

## Fix

按 descriptor 的 scope 分开写：service 级字段（holographic 的 dataPath，必须指向 store.json 文件）放进 services.<providerId>；memory 级字段（defaultTrust/minTrust）放进 body.connection。改完 toggle 该 bundle（enabled=false→true）重载，再查 mnemon_status 的 memorySpaces.total 与 providers[].status。改前备份 state/memory-providers.json，失败回填并重载即可恢复；远程 Provider 里的数据不受注册表影响。

## Verification

改回正确 scope 并重载后 memorySpaces.total 从 0 回到 2（openviking + holographic），两个 Provider status 均 healthy，写入与召回各验证一次成功；对照实验把 dataPath 放回 body.connection 立即复现 total=0。
