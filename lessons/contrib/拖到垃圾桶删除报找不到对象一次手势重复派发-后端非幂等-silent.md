---
title: "（已订正）拖到垃圾桶删除报『找不到对象』：原根因有误，见『delete 先落盘 + 过期 update 竞态』"
domain: "frontend"
tags:
  - "frontend"
  - "react"
  - "drag-drop"
  - "stale-op"
  - "not-found"
  - "dsh-plugin"
status: "superseded"
evidence_level: "E1"
created: "2026-11-08"
updated: "2026-11-09"
source: "intake-4544"
summary_plain: "本课原根因（两条重复 delete 派发）已被抓包证伪并订正，内容并入『delete 先落盘 + 过期 update 竞态』一课。"
trigger: "拖到垃圾桶删除 找不到对象 it_xxx 已订正 见 delete 先落盘 过期 update 竞态 superseded"
verify: "判据已订正：拖一次正常就是 2 条 POST /ops（delete_item 与 update_item(pos)），不要拿「只有 1 条」当成功；看每条响应的 errors 是否为空。"
---

## Problem

把卡片拖到左上角垃圾桶删除后弹「找不到对象：it_xxx / Not found: it_xxx」，而卡片其实已被删除、持久化 state 里该 id 已不存在。

**本课的第一版根因是错的**（写的是「一次手势有两条重复 delete_item 派发 + 后端非幂等」），据此给出的修法（前端只对 delete_item 做 in-flight 去重 + 幂等 delete_item）被报料者用运行时抓包复测证伪，仍报同一个错。

## Root Cause

订正后的根因见 canonical 课：一次拖拽产生的是**两条不同 op** 的 POST /ops —— `delete_item` 与存坐标的 `update_item(pos)`。删除先把条目从 state 移除；随后到达的 `update_item` 走 `findById` 找不到 id 而抛错，`applyOps` 把它收进 errors[] 随 HTTP 200 返回，前端 errors toast 无条件弹。`silent` 只 gate 成功 receipt，压不住。

## Fix

本课不再给出修法，改为指向已订正的 canonical 课：

- [`lessons/contrib/拖到垃圾桶删除后弹找不到对象delete-先落盘-过期存坐标-update-竞态stale-op.md`](https://github.com/Ikalus1988/MisakaNet/blob/main/lessons/contrib/拖到垃圾桶删除后弹找不到对象delete-先落盘-过期存坐标-update-竞态stale-op.md)

修法要点：把抛错的 `update_item` 改为幂等静默（`find` 不到就 `return null`），改完重启 host。

## Verification

订正依据（intake #4546）：抓包 + 本地复现——`delete→update` 报 errors，`update→delete` 与 `delete→delete` 都干净；原课「拖一次只有 1 条 POST」的判据是错的，正常形态就是 2 条，判据应看每条响应的 `errors` 是否为空。
