---
title: "pnpm 被文件锁卡死时的替代路径：把无依赖树包的 tarball 直接解进 node_modules"
domain: "devops"
tags:
  - "pnpm"
  - "eperm"
  - "npm-registry"
  - "tarball"
  - "windows"
  - "plugin-install"
status: "published"
evidence_level: "E1"
created: "2026-11-08"
updated: "2026-11-08"
source: "intake-4553"
summary_plain: "给运行中的 Electron 宿主装一个新插件，`pnpm install` 反复 `ERR_PNPM_EPERM`（rename 临时目录 → 目标被宿主映射）。按常规手法把被锁目录改名让路，下一次 install…"
trigger: "pnpm 被文件锁卡死时的替代路径：零依赖包直接解 tarball 进 node_modules. 给运行中的 Electron 宿主装一个新插件，`pnpm install` 反复 `ERR_PNPM_EPERM`（rename 临时目录 →…"
verify: "`node_modules/<pkg><PATH>` 存在且版本正确；`package.json` 的 bundles/dependencies 与 lockfile 都有该条目；重启后宿主能加载（宿主日志或界面可见其入口）。"
provenance:
  issue: "#4553"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

给运行中的 Electron 宿主装一个新插件，`pnpm install` 反复 `ERR_PNPM_EPERM`（rename 临时目录 → 目标被宿主映射）。按常规手法把被锁目录改名让路，下一次 install 又撞别的包，第三次撞在一个**纯 JS 包**上——说明不是某个原生模块的问题，而是整棵树的对账都会碰锁。而宿主又不能随便关（关掉就没有命令通道了）。

## Root Cause

pnpm 是按"整棵树与 lockfile/`.modules.yaml` 对账"工作的：只要记账与磁盘不一致（比如之前在锁状态下只改了一半），它每次都会尝试重新 import 大量包，每个 import 都是一次"写临时目录再 rename"，于是逐个撞上宿主持有的句柄。这条路在宿主存活时没有稳定解。

## Fix

先确认目标包**没有运行时依赖**（`dependencies` 为空，只有宿主提供的 peerDependencies）。满足就走手工路径：\n1) 从 registry 下 tarball：`https://registry.npmjs.org/<pkg>/-/<pkg>-<ver>.tgz`；\n2) 用 `dist.shasum`（sha1）或 `dist.integrity` 校验；\n3) 解开（`tar -xzf`，Windows 10+ 自带 bsdtar），把包内 `package/` 目录整块移到 `node_modules/<pkg>`；\n4) `pnpm install --lockfile-only` 同步 lockfile（**这个命令不碰 node_modules，不会撞锁**）；\n5) 重启宿主加载。\n因为全程只是"新增一个目录"，没有任何 rename 覆盖，宿主持有的句柄不参与，锁问题不存在。

## Verification

`node_modules/<pkg><PATH>` 存在且版本正确；`package.json` 的 bundles/dependencies 与 lockfile 都有该条目；重启后宿主能加载（宿主日志或界面可见其入口）。
