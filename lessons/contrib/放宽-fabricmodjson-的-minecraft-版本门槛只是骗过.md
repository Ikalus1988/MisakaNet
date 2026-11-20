---
title: "放宽 fabric.mod.json 的 minecraft 版本门槛只是骗过 Loader，跨版本照样崩（NoSuchFieldError: Minecraft 'Screen screen'）"
domain: "development"
tags:
  - "minecraft"
  - "fabric"
  - "mod-compat"
  - "reflection"
status: "published"
evidence_level: "E1"
created: "2026-11-20"
updated: "2026-11-20"
source: "intake-5113"
summary_plain: "Minecraft 26.2 + Fabric 上想跑一个只有 26.1 构建的模组。把 jar 内 fabric.mod.json 的依赖从 \">=26.1 <26.2\" 放宽成 \">=26.1 <26.3\" 之后，Loader…"
trigger: "放宽 fabric.mod.json 的 minecraft 版本门槛只是骗过 Loader，跨版本照样崩（NoSuchFieldError: Minecraft 'Screen screen'）. Minecraft 26.2 + Fabric 上想跑一个只有 26.1 构建的模组。把 jar 内…"
verify: "1) 把 fabric.mod.json 改回原样后 Loader 报不兼容 —— 说明门槛不是病根； 2) javap -p -cp <新版 merged jar> net.minecraft.client.Minecraft 确认旧字段确实不存在（26.2 没有 Screen 字段，只有 gui）； 3) 能进主菜单并加载世界不崩，才算真兼容。"
provenance:
  issue: "#5113"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

Minecraft 26.2 + Fabric 上想跑一个只有 26.1 构建的模组。把 jar 内 fabric.mod.json 的依赖从 ">=26.1 <26.2" 放宽成 ">=26.1 <26.3" 之后，Loader 不再报不兼容，但游戏进到初始化阶段就崩：

NoSuchFieldError: Class net.minecraft.client.Minecraft does not have member field 'net.minecraft.client.gui.screens.Screen screen'
  at vazkii.patchouli.client.handler.BookCrashHandler.appendToCrashReport

更早还有 mixin 落空：
@Mixin target net.minecraft.client.renderer.MultiBufferSource$BufferSource was not found

最坑的是：这个模组把崩溃报告生成器也挂在自己身上，它一崩就把真正的原始异常盖掉了。

## Root Cause

两个独立问题叠加：
1. fabric.mod.json 的 depends 只是声明，Loader 只按它判版本；放宽它不会改动任何字节码。
2. 跨 content 版本（26.1 → 26.2）时 Mojang 挪了 API：屏幕状态不再是 Minecraft 的字段，26.2 里在 Gui 上（Minecraft.gui.screen() / gui.setScreen(...)）；MultiBufferSource$BufferSource 也被移走。旧字节码按旧名访问，运行时才 NoSuchFieldError。

## Fix

不要靠改 metadata 兼容。要么从源码在新版本重编，要么别装。

判断一个二进制能不能跨版本直接搬，命中下面任一条基本没救：
- 带 SystemReport / CrashReport 钩子
- mixin 里写死 @At target 的类名或成员名
- 用到渲染 / GUI / 实体模型这类变动频繁的 API

## Verification

1) 把 fabric.mod.json 改回原样后 Loader 报不兼容 —— 说明门槛不是病根；
2) javap -p -cp <新版 merged jar> net.minecraft.client.Minecraft 确认旧字段确实不存在（26.2 没有 Screen 字段，只有 gui）；
3) 能进主菜单并加载世界不崩，才算真兼容。
