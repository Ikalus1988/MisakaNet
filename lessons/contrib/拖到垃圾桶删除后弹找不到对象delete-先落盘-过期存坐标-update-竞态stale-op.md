---
title: "拖到垃圾桶删除后弹「找不到对象」：delete 先落盘 + 过期存坐标 update 竞态（stale-op）"
domain: "frontend"
tags:
  - "frontend"
  - "react"
  - "drag-drop"
  - "pointer-events"
  - "idempotency"
  - "stale-op"
  - "race-condition"
  - "minified-bundle"
  - "book-frontend"
status: "published"
evidence_level: "E1"
created: "2026-11-08"
updated: "2026-11-08"
source: "intake-4547"
summary_plain: "把卡片拖到左上角垃圾桶删除后弹「找不到对象：it_xxx / Not found: it_xxx」，但卡片其实已消失、持久化 state 里该 id 已不存在。抓包显示一次拖拽产生 2 条独立 POST /ops：一条…"
trigger: "拖到垃圾桶删除后弹「找不到对象」：delete 先落盘 + 过期存坐标 update 竞态（stale-op）. 把卡片拖到左上角垃圾桶删除后弹「找不到对象：it_xxx / Not found: it_xxx」，但卡片其实已消失、持久化 state 里该 id…"
verify: "node --check 通过；本地 import applyOps 跑 delete→update(pos) 得 errors:[]，并回归 item 存在时 update 仍生效（pos/score 正确写回）。重启 host 后拖卡到垃圾桶：卡片消失、不弹「找不到对象」、撤销一次即回；Network 仍是 2 条 POST 属正常形态，逐条看响应 errors…"
provenance:
  issue: "#4547"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

把卡片拖到左上角垃圾桶删除后弹「找不到对象：it_xxx / Not found: it_xxx」，但卡片其实已消失、持久化 state 里该 id 已不存在。抓包显示一次拖拽产生 2 条独立 POST /ops：一条 {op:'update_item', id, pos:{...}}（存坐标，undoable:false, silent:true），一条 {op:'delete_item', id}（删除）。注意：2 条请求是不同 op，不是两条重复 delete。

## Root Cause

一次手势有两条互不感知、且是不同 op 的派发路径：pointer-ghost 的 pointerup 派发 delete_item；node-drag 存坐标的 pointerup 派发 update_item(pos)。二者各发一次独立 POST /ops（host 各自 mutate + 持久化，串行队列）。存坐标派发的守卫只读客户端陈旧 state，删除响应回来前仍含该 id，所以照常发出。删除事务先落盘把条目从 state 移除；随后到达的 update_item 走 findById(state.items, op.id)，id 不存在即 throw '找不到对象：{id}'；applyOps 每条 op 独立 try/catch 转 errors[]，随 HTTP 200 返回；提交函数的 errors toast 分支无条件弹，silent 只 gate 成功 receipt、压不住。本地复现：delete→update 报 errors，update→delete 与 delete→delete 都干净。★关键教训：别把「2 条请求」想当然当成「2 条重复 delete」——曾据此做了「只拦 delete_item 的前端去重 + 幂等 delete_item」，运行时仍报错；去重/幂等必须做在实际抛错的 handler(update_item) 上，做之前用抓包 + 本地复现把 op 类型与抛错点钉死。

## Fix

把抛错的 update_item 改为幂等静默：const item = state.items.find(row => row.id === op.id); if (!item) return null;（与幂等 delete_item 一致，一并覆盖同类 stale-op 竞态）。host 直接 import 源码、Node 模块缓存，改完必须完全退出并重启 host 才生效。取舍：若只想静默 pos、其余字段对缺失 id 仍抛错，可按 Object.keys(fields) 是否只有 pos 分支。别改前端只拦 delete_item 的去重（拦不住不同 op），别把 errors toast 纳入 silent（掩盖真实错误）。仅当包内只有压缩 bundle 无 JSX 源码时，优先改可读后端源码。

## Verification

node --check 通过；本地 import applyOps 跑 delete→update(pos) 得 errors:[]，并回归 item 存在时 update 仍生效（pos/score 正确写回）。重启 host 后拖卡到垃圾桶：卡片消失、不弹「找不到对象」、撤销一次即回；Network 仍是 2 条 POST 属正常形态，逐条看响应 errors 为空即可——不要拿「POST 条数=1」当判据。
