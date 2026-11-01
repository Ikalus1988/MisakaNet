---
title: "pnpm link: 装本地插件目录导致依赖解析不到：Node 向上查找走不到 profile 的 node_modules，改用 file:"
domain: "devops"
tags:
  - "dsh"
  - "pnpm"
  - "plugin"
  - "node-module-resolution"
  - "symlink"
status: "published"
evidence_level: "E1"
created: "2026-11-01"
updated: "2026-11-01"
source: "intake-4227"
summary_plain: "把本地插件目录用 link: 协议装进 DSH profile 后，它声明的 dependencies / peerDependencies 全部解析不到，插件不生效。"
trigger: "pnpm link: 装本地插件目录导致依赖解析不到：Node 向上查找走不到 profile 的 node_modules，改用 file:。"
verify: "① Get-Item node_modules\\<pkg> 的 LinkType 为空（真实目录）； ② 从安装位置能解析到它声明的 dependencies 与 peerDependencies（require.resolve，或在祖先 node_modules 中找到）； ③ 宿主重载后插件功能可用：路由有响应、客户端界面出现。"
provenance:
  issue: "#4227 + #4243"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

把本地插件目录用 `link:` 协议装进 DSH profile 后，插件不生效：它声明的 `dependencies` / `peerDependencies` 全部解析不到，直到加载或调用时才炸，宿主甚至可能在启动阶段就失败。

## Root Cause

link: 装的是符号链接。Node 解析模块默认走真实路径（未开启 --preserve-symlinks），于是从 plugins/<pkg>/lib 向上找 node_modules 只会经过 plugins/node_modules、.dsh/node_modules 等，永远不会经过 profiles/<profile>/node_modules。插件声明的 dependencies 因此全部解析不到，直到加载或调用时才炸，甚至可能让宿主启动阶段失败。peerDependencies 走同一套查找：宿主提供的包（如 @deepseek-ai/*）只在 profile 的 node_modules 里，从真实路径向上永远看不到。file: 会把包真正安装进 profile 的 node_modules，向上查找自然命中。

## Fix

本地目录依赖一律用 file: 协议：
  dsh plugin --profile <profile> add "file:<绝对路径>"
pnpm 会 pack 该目录并安装进依赖树，连同它的 dependencies 一起解析。
若不想直接把目录交给 file:，也可以把插件打成 .tgz 再装（`file:./pkg.tgz`）：tgz 会解到 profile 的 node_modules 里，peer 也从正确位置向上解析。
若确实必须用 link:，则要在插件的真实目录下自建 node_modules，并把它需要而 profile 里才有的包链进去（manually shim），否则运行时必然解析失败。

## Verification

① Get-Item node_modules\<pkg> 的 LinkType 为空（真实目录）；
② 从安装位置能解析到它声明的 dependencies 与 peerDependencies（require.resolve，或在祖先 node_modules 中找到）；
③ 宿主重载后插件功能可用：路由有响应、客户端界面出现。
