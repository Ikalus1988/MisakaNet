---
title: "DSH 里两个 bundle patch 的 id 撞车会互相覆盖，且 pnpm 重装抹掉本地修复"
domain: "devops"
tags:
  - "dsh"
  - "cordis"
  - "patch"
  - "plugin-id"
  - "id-collision"
  - "overlay"
status: "published"
evidence_level: "E1"
created: "2026-11-02"
updated: "2026-11-02"
source: "intake-4242"
summary_plain: "同时装两个 DSH 插件时，其中一方 cordis.patch.yml 注册的 id 与另一方重复（例如都叫 ui-task-board 或…"
trigger: "DSH 里两个 bundle patch 的 id 撞车会互相覆盖，且 pnpm 重装抹掉本地修复. 同时装两个 DSH 插件时，其中一方 cordis.patch.yml 注册的 id 与另一方重复（例如都叫 ui-task-board 或…"
verify: "重启后两个插件同时生效，功能都在；不再出现「装了但看不到」的现象。"
provenance:
  issue: "#4242"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

同时装两个 DSH 插件时，其中一方 cordis.patch.yml 注册的 id 与另一方重复（例如都叫 ui-task-board 或 memory），结果只有一个生效、另一个被静默顶掉，界面上表现为某个面板或工具凭空消失，没有任何冲突提示。

## Root Cause

DSH 的 cordis patch 按 id 覆盖：后应用的 patch 会顶掉同 id 的行。id 全局唯一是隐式契约，加载器不检测冲突、也不告警。

## Fix

查 node_modules/<包名><PATH> 找出重复 id，把冲突方的 id 改掉并留 .bak；但 pnpm 重装或升级该包会覆盖这个改动，所以要么锁版本，要么向上游提 issue 让作者换 id。

## Verification

重启后两个插件同时生效，功能都在；不再出现「装了但看不到」的现象。
