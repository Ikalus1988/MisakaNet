---
title: "Vite/Rollup 构建报 is not exported by：CommonJS 文件被 ESM 命名导入"
domain: "windows"
tags:
  - "problem"
  - "js"
  - "vite"
status: "published"
evidence_level: "E1"
created: "2026-11-11"
updated: "2026-11-11"
source: "intake-4672"
summary_plain: "Vite/Rollup 构建报 is not exported by：CommonJS 文件被 ESM 命名导入"
trigger: "Vite/Rollup 构建报 is not exported by：CommonJS 文件被 ESM 命名导入"
verify: "三路验证：`npm run build` 构建通过 ✓ / vitest 全量绿 ✓ / Node 直接 import 该模块可用 ✓（脚本路径）。另注：同文件**并行编辑**会互相覆盖（编辑各自整文件读写，后写胜出）——串行编辑+落盘核验（该点语料已有 windows-parallel-edit-replacefilew-win32-32）。"
provenance:
  issue: "#4672"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

JS 项目（Vite/Rollup 打包 + 共享工具层）构建报：`"X" is not exported by "src/.../config/index.js"`——该文件是 **CommonJS**（module.exports + require 载 JSON），被 ESM 源码用命名导入引用。单测（vitest）与 Node 直跑都过，只有生产构建炸。

## Root Cause

Rollup 的导出互操作只给 **node_modules 里的 CJS**（commonjs 插件）；**源码树内的 .js CJS 文件**不会被转译成 ESM，命名/默认导入都取不到导出。CJS-ESM 混放的源码树在测试链（esbuild 宽容）下全绿，到打包器（严格互操作）才炸——两套解析器的宽容度差异是假绿温床。

## Fix

金标准/配置类数据改 **JSON 直引 + import 属性**：`import RULES from './x.json' with { type: 'json' }`——Node 22 ✓、Vite/Rollup ✓、Vitest ✓ 三路通吃。（退路：把表做成 ESM .js 模块；或默认导入+取值，但部分打包器对源码 CJS 连默认导出都不给。）

## Verification

三路验证：`npm run build` 构建通过 ✓ / vitest 全量绿 ✓ / Node 直接 import 该模块可用 ✓（脚本路径）。另注：同文件**并行编辑**会互相覆盖（编辑各自整文件读写，后写胜出）——串行编辑+落盘核验（该点语料已有 windows-parallel-edit-replacefilew-win32-32）。
