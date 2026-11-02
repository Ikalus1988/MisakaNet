---
title: "DSH 插件 peerDependencies 不满足时被静默跳过：装上了但完全不加载"
domain: "devops"
tags:
  - "dsh"
  - "peer-dependencies"
  - "version"
  - "plugin-not-loading"
  - "silent-skip"
status: "published"
evidence_level: "E1"
created: "2026-11-02"
updated: "2026-11-02"
source: "intake-4249"
summary_plain: "插件装好了，node_modules 里有、package.json 的 dependencies 和 dsh.profile.bundles 都写了，重启后插件完全没生效，而且没有任何报错。"
trigger: "DSH 插件 peerDependencies 不满足时被静默跳过：装上了但完全不加载. 插件装好了，node_modules 里有、package.json 的 dependencies 和 dsh.profile.bundles…"
verify: "重启后插件页能看到该插件且状态是运行中。"
provenance:
  issue: "#4249"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

插件装好了，node_modules 里有、package.json 的 dependencies 和 dsh.profile.bundles 都写了，重启后插件完全没生效，而且没有任何报错。

## Root Cause

DSH 的加载器校验 peerDependencies，宿主版本不在插件声明的范围内就直接跳过该插件（例如插件要求 dsh-tools 0.1.x 而宿主是 0.2.x），既不降级也不告警。

## Fix

装之前看插件 package.json 的 peerDependencies 和 README 的版本兼容表，装对应版本（作者一般留了旧版分支）；也可以先用插件市场的兼容性检查接口确认。

## Verification

重启后插件页能看到该插件且状态是运行中。
