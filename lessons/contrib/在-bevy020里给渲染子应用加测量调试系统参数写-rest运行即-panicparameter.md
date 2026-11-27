---
title: "在 Bevy（0.20）里给渲染子应用加测量/调试系统，参数写 `Res<T>`，运行即 panic：`Parameter Res<T> fai"
domain: "mcp"
tags:
  - "insert_resource"
  - "app.insert_resource-x.clone"
  - "bevy"
status: "published"
evidence_level: "E1"
created: "2026-11-27"
updated: "2026-11-27"
source: "intake-5862"
summary_plain: "在 Bevy（0.20）里给渲染子应用加测量/调试系统，参数写 `Res<T>`，运行即 panic：`Parameter Res<T> failed validation: Resource does not…"
trigger: "bevy Res failed validation Resource does not exist render sub-app SubApp insert_resource"
verify: "渲染世界系统能读到资源、不再 panic 并按预期写回共享句柄；故意只插主世界可复现原 panic（回归抓手）。 render-world system with Res<T> runs without panic when the resource is inserted into both worlds; single-world insert reproduces the panic"
provenance:
  issue: "#5862"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

在 Bevy（0.20）里给渲染子应用加测量/调试系统，参数写 `Res<T>`，运行即 panic：`Parameter Res<T> failed validation: Resource does not exist`——而资源明明已经 `app.insert_resource(..)` 插进 App 了。

## Root Cause

Bevy 的 render 子应用（SubApp）拥有**独立的资源世界**：主 App 的 `insert_resource` 只进主世界，跑在渲染 schedule 里的系统在渲染世界解析资源，两个世界互不可见。资源放错世界 = 渲染系统永远见不到。

## Fix

同一资源两个世界都插：主世界 `app.insert_resource(x.clone())` 之外，再 `app.get_sub_app_mut(RenderApp).insert_resource(x.clone())` 然后 `add_systems(Render, system)`（资源用 Arc<Mutex<..>> 之类共享句柄跨世界回传结果）。按「不静默吞错」原则不要用 Option<Res<T>> 把缺资源糊过去——缺资源就是配置错误。

## Verification

渲染世界系统能读到资源、不再 panic 并按预期写回共享句柄；故意只插主世界可复现原 panic（回归抓手）。

render-world system with Res<T> runs without panic when the resource is inserted into both worlds; single-world insert reproduces the panic
