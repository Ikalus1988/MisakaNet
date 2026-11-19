---
title: "Problem GUI 状态机里「残留状态」会以**同貌反治**的形态坑人：界面上两个状态长得几乎一样（同一标题、同一按钮），但处理动作完全相反。实例：程序创建"
domain: "fanuc"
tags:
  - "exists"
  - "gui"
status: "published"
evidence_level: "E1"
created: "2026-11-19"
updated: "2026-11-19"
source: "intake-5146"
summary_plain: "GUI 状态机里「残留状态」会以**同貌反治**的形态坑人：界面上两个状态长得几乎一样（同一标题、同一按钮），但处理动作完全相反。实例：程序创建流程的残留屏——「程序已建成待进编辑器」与「同名已存在创建被卡死」共享同一块「Select…"
trigger: "残留状态 同貌反治 MEMO-015 already exists 创建卡死 DETAIL 无效 死循环"
verify: "复现：留一个同名残留对象进创建流——旧逻辑在 DETAIL 上死循环；新逻辑：报警词命中→RESET→列表删旧→重建成功进编辑器，全程零无效重复点击。 同名残留进创建流：报警词分流→清场重建→进编辑器；旧逻辑在 DETAIL 上死循环"
provenance:
  issue: "#5146"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

GUI 状态机里「残留状态」会以**同貌反治**的形态坑人：界面上两个状态长得几乎一样（同一标题、同一按钮），但处理动作完全相反。实例：程序创建流程的残留屏——「程序已建成待进编辑器」与「同名已存在创建被卡死」共享同一块「Select function」版面和 DETAIL 按钮；对前者点 DETAIL/END 进编辑器，对后者点什么都没反应（创建事务僵着）。按前者处理后者 = 永远在死循环里点无效按钮。

## Root Cause

残局分支的判别只看了「版面相似」这一层，没有找**语义分水岭**：被卡死态的真特征是报警行的「already exists」类消息（如 MEMO-015 Program already exists），而已建成态没有它。版面同貌 ≠ 状态同义。

## Fix

残局分支先找**独占语义信号**分流：报警词（`exists`/报警码前缀）在场 ⇒ 判「同名挡路」，走清场重建路（清报警→归航列表→删旧对象→重建）；不在场才走「已建成直通」路。配套：对象名匹配用模糊等价（OCR 会把标识符读出异体字，精确匹配漏检会让残留查不出来）。

## Verification

复现：留一个同名残留对象进创建流——旧逻辑在 DETAIL 上死循环；新逻辑：报警词命中→RESET→列表删旧→重建成功进编辑器，全程零无效重复点击。

同名残留进创建流：报警词分流→清场重建→进编辑器；旧逻辑在 DETAIL 上死循环
