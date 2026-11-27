---
title: "在 Bevy（0.20 系）应用里给 `App` 挂插件时写了两次 `app.add_plugins(DefaultPlugins.set(Pl"
domain: "mcp"
tags:
  - "defaultplugins"
  - "in"
  - "with"
status: "published"
evidence_level: "E1"
created: "2026-11-27"
updated: "2026-11-27"
source: "intake-5885"
summary_plain: "在 Bevy（0.20 系）应用里给 `App` 挂插件时写了两次…"
trigger: "bevy DefaultPlugins plugin was already added in application add_plugins twice panic"
verify: "复现：两次 add_plugins(DefaultPlugins...) 运行即 panic（编译期零警告）；改为单次挂载链 .set 后同一应用正常起跑、两组配置都生效（各自的 override 可在运行行为上验证）。 app with two add_plugins(DefaultPlugins...) panics at startup; single add_plugins with…"
provenance:
  issue: "#5885"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

在 Bevy（0.20 系）应用里给 `App` 挂插件时写了两次 `app.add_plugins(DefaultPlugins.set(PluginA{...})).add_plugins(DefaultPlugins.set(PluginB{...}))`——想分别覆盖两组配置。**编译完全通过、clippy 全绿**，运行第一帧直接 panic：`Error adding plugin ... in group DefaultPlugins: plugin was already added in application`。

## Root Cause

`DefaultPlugins` 是插件组，`add_plugins` 会把整组装进 App；第二次 `add_plugins(DefaultPlugins...)` 尝试重复装组内每个插件，启动时才检查报重复。多组配置的正确姿势是**一次 add_plugins、链式 .set 覆盖**：`add_plugins(DefaultPlugins.set(A).set(B))`——重复挂载是纯运行时错误，静态检查发现不了。

## Fix

把 `add_plugins(DefaultPlugins.set(A{..})).add_plugins(DefaultPlugins.set(B{..}))` 改为
`add_plugins(DefaultPlugins.set(A{..}).set(B{..}))`（一次挂载、多个 `.set` 链式覆盖各自配置）。
排查提示：这个 panic 发生在 App 启动最早期，信息里带插件组名——见到 "plugin was already added in application" 直接全文搜 `add_plugins(DefaultPlugins` 个数即得。

## Verification

复现：两次 add_plugins(DefaultPlugins...) 运行即 panic（编译期零警告）；改为单次挂载链 .set 后同一应用正常起跑、两组配置都生效（各自的 override 可在运行行为上验证）。

app with two add_plugins(DefaultPlugins...) panics at startup; single add_plugins with chained .set() runs with both overrides applied
