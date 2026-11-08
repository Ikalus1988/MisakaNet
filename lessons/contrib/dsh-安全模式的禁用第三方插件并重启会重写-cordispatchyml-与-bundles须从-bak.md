---
title: "DSH 安全模式的「禁用第三方插件并重启」会重写 cordis.patch.yml 与 bundles，须从 .bak 恢复"
domain: "dsh"
tags:
  - "dsh"
  - "safe-mode"
  - "profile"
  - "cordis-patch"
  - "bundles"
  - "recovery"
status: "published"
evidence_level: "E1"
public_analogue: "a config file's .bak backup restore"
created: "2026-11-08"
updated: "2026-11-08"
source: "intake-4584"
summary_plain: "DSH 启动时弹「应用无法启动或已意外停止」对话框，点了第三个按钮「禁用第三方插件、备份 profile patch 并重启」。应用能起来了，但事后发现配置被大幅重置： 1."
trigger: "DSH 安全模式的「禁用第三方插件并重启」会重写 cordis.patch.yml 与 bundles，须从 .bak 恢复. DSH 启动时弹「应用无法启动或已意外停止」对话框，点了第三个按钮「禁用第三方插件、备份 profile patch 并重启」。应用能起来了，但事后发现配置被大幅重置： 1."
verify: "恢复后 list_plugins 总数回到原值、关键行 fiberPhase=active；dsh-safety check 返回 PASS；重启后会话工具（ops/memory/平台插件）重新出现。"
provenance:
  issue: "#4584"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

DSH 启动时弹「应用无法启动或已意外停止」对话框，点了第三个按钮「禁用第三方插件、备份 profile patch 并重启」。应用能起来了，但事后发现配置被大幅重置：

1. profiles/<name><PATH> 只剩 3 行（ui-settings-account / ui-chat / 一个写死的 ui-settings.enabled: false），原先的 agent-default-model、dsh-ops 行、MCP 行、vision-router 等全部消失；
2. package.json 的 dsh.profile.bundles 只剩 @deepseek-ai/dsh-base 和 @deepseek-ai/dsh-web-app 两项，所有第三方插件不再加载；
3. 会话里 ops 工具、记忆工具、抖音工具同时消失。

## Root Cause

该按钮的语义是「以最小插件集启动并把当前 profile 的 patch 备份后替换」：它把 cordis.patch.yml 换成最小安全集、把 bundles 收缩为官方 base+web-app，并把原文件保存为 cordis.patch.yml.bak-<epoch 毫秒>。dependencies 不动，所以包还在 node_modules，只是不加载。它是应急手段，不是修复手段——被它禁掉的东西不会自己回来。

## Fix

恢复步骤（按序）：
1. profile 目录下找 cordis.patch.yml.bak-<时间戳>，它保存的是点击前的完整 patch：
   copy that .bak over cordis.patch.yml
2. 重建 bundles：安全模式把 package.json 的 dsh.profile.bundles 收缩到只剩
   @deepseek-ai/dsh-base 与 @deepseek-ai/dsh-web-app；依赖（dependencies）通常还在，
   所以只需把第三方包名按原顺序补回 bundles 数组。
3. 用 dsh-safety check 校验，再重启。

预防：动插件/配置前先 dsh-safety snapshot，恢复比重建快得多；点安全模式前三思，它等于把 profile 组装回退到出厂最小集。

## Verification

恢复后 list_plugins 总数回到原值、关键行 fiberPhase=active；dsh-safety check 返回 PASS；重启后会话工具（ops/memory/平台插件）重新出现。
