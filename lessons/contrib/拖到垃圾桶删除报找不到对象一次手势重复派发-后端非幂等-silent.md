---
title: "拖到垃圾桶删除报『找不到对象』：一次手势重复派发 + 后端非幂等 + silent 压不住 errors"
domain: "frontend"
tags:
  - "book-frontend"
  - "frontend"
  - "react"
  - "drag-drop"
  - "idempotency"
  - "duplicate-dispatch"
  - "not-found"
  - "dsh-plugin"
  - "minified-bundle"
status: "published"
evidence_level: "E1"
created: "2026-11-08"
updated: "2026-11-08"
source: "intake-4544"
summary_plain: "DSH 插件（灵感卡看板类）把卡片拖到左上角垃圾桶删除后弹『找不到对象：it_xxxx / Not found: it_xxxx』错误，但卡片其实已被删除、持久化 state 里已无该 id。原始报错来自后端…"
trigger: "拖到垃圾桶删除报『找不到对象』：一次手势重复派发 + 后端非幂等 + silent 压不住 errors. DSH 插件（灵感卡看板类）把卡片拖到左上角垃圾桶删除后弹『找不到对象：it_xxxx / Not found: it_xxxx』错误，但卡片其实已被删除、持久化 state…"
verify: "node --check 退出 0；抽取真实函数注入桩做功能测试（同 id 并发→1 次 POST、不同 id/串行同 id/混合批次→正常放行、批次内重复 id 折叠）；字节级校验 orig.replace(old,new)===cur 为真；DevTools Network 拖一次只 1 条 POST /ops、撤销一次卡片即回。"
provenance:
  issue: "#4544"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

DSH 插件（灵感卡看板类）把卡片拖到左上角垃圾桶删除后弹『找不到对象：it_xxxx / Not found: it_xxxx』错误，但卡片其实已被删除、持久化 state 里已无该 id。原始报错来自后端 findById：throw new Error('找不到对象：{id}')，由 applyOps 收集进 errors[] 随 HTTP 200 正常返回。给删除调用加 silent 参数无效。包内只有压缩后的 dist/client.js，无 JSX 源码、无 scripts/build.mjs。

## Root Cause

三层叠加：(1) 一次拖动手势有两条互不感知的 delete_item 派发路径 —— pointer-ghost 的 pointerup 几何命中垃圾桶，以及原生 HTML5 drag 的垃圾桶 onDrop（dataTransfer 读 id），都走同一个中央提交函数且无去重；(2) 后端 delete_item 非幂等，用 findById(state.items, op.id) 找不到就抛错，applyOps 把异常转 errors[] 随 HTTP 200 返回，第二条 delete 在已删除的 state 上必然踩中；(3) 提交函数里 silent 只 gate 成功 receipt 的 toast，errors 分支无条件弹错误提示。state 里 grep 不到该 id 即证明第一次删除已成功落盘。

## Fix

(1) 后端必做兜底：delete_item 改为 state.items.find(row=>row.id===op.id)，找不到只清残留关联数据并 return null，不抛错；host 直接 import 源码且有 Node 模块缓存，改完必须重启 host 才生效。(2) 前端治本：在中央提交函数按 op id 做 in-flight 去重 —— 进入时对带 id 的 delete_item 记 guard[id]、已在 guard 中的过滤掉，await 返回后（成功/异常都）delete guard[id]，其它 op 与混合批次放行；这样挡并发重复而不误挡串行再删。(3) 压缩 bundle 定点改：Get-Content -Raw 整读、抽函数原文、确认替换串唯一=1、先 Copy-Item 字节备份、String.Replace、UTF8Encoding($false) 无 BOM 写回保持 LF、node --check，失败自动从备份还原。别把 errors toast 也纳入 silent（会掩盖真实错误）。

## Verification

node --check 退出 0；抽取真实函数注入桩做功能测试（同 id 并发→1 次 POST、不同 id/串行同 id/混合批次→正常放行、批次内重复 id 折叠）；字节级校验 orig.replace(old,new)===cur 为真；DevTools Network 拖一次只 1 条 POST /ops、撤销一次卡片即回。
