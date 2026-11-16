---
title: "Windows 上用 pnpm 构建 monorepo 时，默认 isolated linker 报 `[ERR_PNPM_SYMLINK_FAILED] [s"
domain: "windows"
tags:
  - "mv"
  - "rm"
  - "fts_read"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4768"
summary_plain: "Windows 上用 pnpm 构建 monorepo 时，默认 isolated linker 报 `[ERR_PNPM_SYMLINK_FAILED] [symlinkAllModules] Maximum call stack…"
trigger: "Windows 上用 pnpm 构建 monorepo 时，默认 isolated linker 报 `[ERR_PNPM_SYMLINK_FAILED] [s. symlinkAllModules] Maximum call stack size exceeded`；改用…"
verify: "`pnpm build:all` 输出各包 `✓ built`，产物 `dist/index.mjs` 可 `node dist/index.mjs` 启动，WebUI 端口 HTTP 200。 pnpm build:all 全部包构建成功，dist/index.mjs 启动后 WebUI 返回 200"
provenance:
  issue: "#4768"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

Windows 上用 pnpm 构建 monorepo 时，默认 isolated linker 报 `[ERR_PNPM_SYMLINK_FAILED] [symlinkAllModules] Maximum call stack size exceeded`；改用 `--config.node-linker=hoisted` 能装完，但顶层被提升成 entities@4.5.0，vite 8 构建报 `"./decode" is not exported under the conditions ["node","default","import"] from package entities`。

## Root Cause

hoisted linker 不再保留每个包的隔离依赖版本，某个依赖需要 entities@6（导出 `./decode`）却被解析到顶层 4.5.0。之前那次 isolated 安装是在一个残留的旧 node_modules 上进行的，pnpm 认为状态一致（Already up to date），没有真正重建链接。

## Fix

1) 把旧依赖目录整体挪走：`mv node_modules node_modules.hoisted`（在 Windows 深路径下直接 `rm -rf` 会 `fts_read failed`）；
2) 再跑一次 `pnpm install --config.node-linker=isolated`，让 pnpm 从零建立隔离树（大仓约 500 个包，几秒完成）；
3) `pnpm build:all` 前确保 `pnpm` 在 PATH 上（构建脚本里 `prepare: pnpm run build` 会调用它）；沙箱环境下 pnpm 跑 lifecycle 会 `spawn EPERM`，需在完全权限下构建。

## Verification

`pnpm build:all` 输出各包 `✓ built`，产物 `dist/index.mjs` 可 `node dist/index.mjs` 启动，WebUI 端口 HTTP 200。

pnpm build:all 全部包构建成功，dist/index.mjs 启动后 WebUI 返回 200
