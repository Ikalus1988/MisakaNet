---
title: "Windows 机器上用 npm 安装 devDependencies（typescript / wrangler 等），npm 输出 \"changed 1 p"
domain: "windows"
tags:
  - "windows"
  - "npm"
  - "devdependencies"
status: "published"
evidence_level: "E1"
created: "2026-11-02"
updated: "2026-11-02"
source: "intake-4136"
summary_plain: "Windows 机器上用 npm 安装 devDependencies（typescript / wrangler 等），npm 输出 \"changed 1 package, and audited 1 package in 3s /…"
trigger: "Windows 机器上用 npm 安装 devDependencies（typescript / wrangler 等），npm 输出 \"changed 1 p. Windows 机器上用 npm 安装 devDependencies（typescript / wrangler 等），npm 输出 \"changed…"
verify: "在同一条命令前加 NODE_ENV=development 与 --include=dev 后重装：node_modules 下出现顶层包与 .bin 软链，`npm ls --depth=0` 列出全部 devDependencies，lockfile 从 2 个条目涨到 92 个条目（按 registry.npmjs.org 解析）。"
provenance:
  issue: "#4136"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

Windows 机器上用 npm 安装 devDependencies（typescript / wrangler 等），npm 输出 "changed 1 package, and audited 1 package in 3s / found 0 vulnerabilities"，看起来成功，但 node_modules 里只有几个 scoped 空目录、没有顶层包、node_modules/.bin 也没生成，`npm ls --depth=0` 显示 (empty)。 反复 npm install / npm ci 都一样。

## Root Cause

根因是该机器环境变量 NODE_ENV=production，npm 因此设置 omit=dev，把 devDependencies 全部跳过；

## Fix

安装时显式带上 `--include=dev`（或把 NODE_ENV 设为 development）。验证判据：`npm ls --depth=0` 能列出 devDependencies 里的每个包，`node_modules/.bin/tsc` 存在，且 lockfile 的 packages 里出现 `node_modules/<pkg>` 条目。

## Verification

在同一条命令前加 NODE_ENV=development 与 --include=dev 后重装：node_modules 下出现顶层包与 .bin 软链，`npm ls --depth=0` 列出全部 devDependencies，lockfile 从 2 个条目涨到 92 个条目（按 registry.npmjs.org 解析）。
