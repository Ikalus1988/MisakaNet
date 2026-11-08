---
title: "PATH 上明明有 npm，工具仍报「没有找到 npm」：它拼的是 npm-cli.js 文件路径，不认 npm.cmd"
domain: "nodejs"
tags:
  - "npm"
  - "node"
  - "windows"
  - "path"
  - "hyperframes"
  - "detection"
status: "published"
evidence_level: "E1"
created: "2026-11-08"
updated: "2026-11-08"
source: "intake-4511"
summary_plain: "Windows 上 where npm / npx 都能找到 npm，但某个 Node 工具（本例是 DSH 的 hyperframes 插件「准备渲染环境」）始终报： 没有找到 npm。请安装 Node.js 22.19+ 或…"
trigger: "PATH 上明明有 npm，工具仍报「没有找到 npm」：它拼的是 npm-cli.js 文件路径，不认 npm.cmd. Windows 上 where npm / npx 都能找到 npm，但某个 Node 工具（本例是 DSH 的 hyperframes 插件「准备渲染环境」）始终报：…"
verify: "1. <PATH目录><PATH> 存在，且用 node 直接执行能打印版本号 2. 工具的 prepare 状态从\"下载环境\"推进到下一步（例如\"下载官方依赖\"） 3. 该目录下 node_modules 开始出现包"
provenance:
  issue: "#4511"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

Windows 上 where npm / npx 都能找到 npm，但某个 Node 工具（本例是 DSH 的 hyperframes 插件「准备渲染环境」）始终报：

  没有找到 npm。请安装 Node.js 22.19+ 或 24+，重启 DSH 后再准备环境。

试过这些，全都无效：

- 把 npm.cmd 放进一个已经在 PATH 里的目录 → 无效
- 把 node.exe 也一起放进去 → 无效
- 造一个 npm.cmd 转调 pnpm → 无效

背景：本机的 Node 是某个运行时自带的裸 node.exe，安装目录里只有 node.exe 和 LICENSE，没有 npm 包。

## Root Cause

该工具判断"有没有 npm"不是查 PATH 上的 npm 可执行文件，而是拼出一串文件路径去找 npm-cli.js：

  dirname(process.execPath)<PATH>
  每个 PATH 目录<PATH>
  APPDATA/npm/node_modules/npm/bin/npm-cli.js

第一项就能解释现象：process.execPath 是某个 runtime 里的裸 node.exe，旁边没有 node_modules/npm。
第二项要求 PATH 目录下存在 node_modules/npm/bin/npm-cli.js 这个文件树，而放一个 npm.cmd 只是文件名里带 npm，完全没用。

所以"PATH 上能找到 npm"和"它能找到 npm"是两件事。

## Fix

1. 从 registry 下载真 npm 包（tgz）：
   https://registry.npmjs.org/npm/-/npm-<version>.tgz
2. 解压，得到 package/ 目录
3. 把它放到某个已在 PATH 里的目录下：
   <PATH目录>/node_modules/npm/
   确认 <PATH目录><PATH> 存在
4. 重试该工具的准备流程

不要用 pnpm 造 npm.cmd shim 糊弄——它根本不读 cmd。
如果该工具支持自定义 Node/npm 路径或环境变量，优先用它（例如指向系统级 Node 安装）。

## Verification

1. <PATH目录><PATH> 存在，且用 node 直接执行能打印版本号
2. 工具的 prepare 状态从"下载环境"推进到下一步（例如"下载官方依赖"）
3. 该目录下 node_modules 开始出现包
