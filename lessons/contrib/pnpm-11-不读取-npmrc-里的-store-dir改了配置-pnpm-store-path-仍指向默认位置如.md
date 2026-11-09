---
title: "pnpm 11 不读取 `~/.npmrc` 里的 `store-dir`，改了配置 `pnpm store path` 仍指向默认位置（如 <PATH> C"
domain: "dsh"
tags:
  - "pnpm"
  - "npmrc"
  - "store"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-3840"
summary_plain: "pnpm 11 不读取 `~/.npmrc` 里的 `store-dir`，改了配置 `pnpm store path` 仍指向默认位置（如 <PATH> C 盘。"
trigger: "pnpm 11 不读取 `~/.npmrc` 里的 `store-dir`，改了配置 `pnpm store path` 仍指向默认位置（如 <PATH> C. pnpm 11 不读取 `~/.npmrc` 里的 `store-dir`，改了配置 `pnpm store path` 仍指向默认位置（如 <PATH>…"
verify: "在项目目录跑 `pnpm store path` 输出新路径；安装新包时旧 store 目录文件数不变，新 store 增长。"
provenance:
  issue: "#3840"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

pnpm 11 不读取 `~/.npmrc` 里的 `store-dir`，改了配置 `pnpm store path` 仍指向默认位置（如 <PATH> C 盘。

## Root Cause

最后发现 pnpm 11 的 workspace 配置优先，且 .npmrc 的 store-dir 不再生效。

## Fix

把设置写进 profile 的 `pnpm-workspace.yaml`，用 camelCase 键：`storeDir: <PATH> packages/nodeLinker/autoInstallPeers）。改完在 profile 目录执行 `pnpm store path` 验证；已安装过的项目还需把 node_modules/.modules.yaml 里的 storeDir 与 virtualStoreDir 一并改到新位置，否则 pnpm 会认为依赖来自别处。

## Verification

在项目目录跑 `pnpm store path` 输出新路径；安装新包时旧 store 目录文件数不变，新 store 增长。
