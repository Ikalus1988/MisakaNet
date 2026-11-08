---
title: "DSH 插件配置写进 cordis.patch.yml 却不生效：id 必须是插件的 export const name，不是包名"
domain: "dsh"
tags:
  - "dsh"
  - "cordis"
  - "plugin"
  - "config"
  - "id"
  - "silent-failure"
status: "published"
evidence_level: "E1"
created: "2026-11-08"
updated: "2026-11-08"
source: "intake-4510"
summary_plain: "在 DSH profile 的 cordis.patch.yml 里给插件写配置，重启后插件行为完全没变，像配置根本没被读到，但也不报任何错。"
trigger: "DSH 插件配置写进 cordis.patch.yml 却不生效：id 必须是插件的 export const name，不是包名. 在 DSH profile 的 cordis.patch.yml 里给插件写配置，重启后插件行为完全没变，像配置根本没被读到，但也不报任何错。"
verify: "1. patch 里的 id 与插件源码 export const name 完全一致 2. 重启后插件自检工具输出正常（例如 ffmpeg/ffprobe 都能执行） 3. 若仍不生效，检查是否有另一个 patch 条目占用了同一个 id"
provenance:
  issue: "#4510"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

在 DSH profile 的 cordis.patch.yml 里给插件写配置，重启后插件行为完全没变，像配置根本没被读到，但也不报任何错。

当时的写法（错的）：

- id: dsh-ffmpeg
  name: dsh-ffmpeg
  config:
    ffmpegPath: '<abs path><PATH>'
    ffprobePath: '<abs path><PATH>'

现象：插件自检仍然报 spawn ffmpeg ENOENT。试过把 id 写成包名、加/去掉 dsh- 前缀，都不生效。

## Root Cause

cordis 的 patch 是按 loader id 去匹配插件的，而 loader id 来自插件模块导出的 export const name，不是 npm 包名。

以 dsh-ffmpeg 为例，它的 package.json name 是 "dsh-ffmpeg"，但入口文件里写的是：

  export const name = 'ffmpeg';

所以 patch 的 id 必须是 ffmpeg，写 dsh-ffmpeg 就匹配不上。id 对不上时 patch 被静默跳过，不报错、不警告，表现为"配置写了但毫无反应"。

注意与另一种失败区分：两个 bundle patch 用同一个 id 会互相覆盖，那是"撞车"；这里是"id 写错导致静默不生效"。

## Fix

1. 打开插件入口文件（package.json 的 main 字段指向的那个）
2. 找 export const name = '...'，记下这个字符串
3. 把 profile 的 cordis.patch.yml 里该条目的 id 改成这个值
4. 用 YAML 解析器验一遍语法，再重启 DSH
5. 重启后跑插件自带的自检工具（本例是 ffmpeg_health），确认配置被读到

参考：插件如果自带 cordis.patch.yml，里面 insert 的 id 就是正确写法，直接抄。

## Verification

1. patch 里的 id 与插件源码 export const name 完全一致
2. 重启后插件自检工具输出正常（例如 ffmpeg/ffprobe 都能执行）
3. 若仍不生效，检查是否有另一个 patch 条目占用了同一个 id
