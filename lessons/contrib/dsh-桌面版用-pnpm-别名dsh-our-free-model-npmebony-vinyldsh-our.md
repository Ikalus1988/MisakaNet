---
title: "DSH 桌面版用 pnpm 别名装插件：Host 半身起来了，client 半身没注册"
domain: "dsh"
tags:
  - "dsh"
  - "pnpm"
  - "our"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4630"
summary_plain: "DSH 桌面版用 pnpm 别名装插件：Host 半身起来了，client 半身没注册"
trigger: "DSH 桌面版用 pnpm 别名装插件：Host 半身起来了，client 半身没注册"
verify: "抓 /plugins/?? 组合请求确认 <行名>/client.js 在内；重启后设置页出现该插件入口。"
provenance:
  issue: "#4630"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

DSH 桌面版用 pnpm 别名（"dsh-our-free-model": "npm:@ebony-vinyl/dsh-our-free-model@2.8.3"）安装声明了 dsh.client 的插件后，插件 Host 半身正常（/api/our-free-model/summary 返回 401 而非 404，插件数据目录照常写入），但浏览器半身从不加载：设置页里该插件的分区入口与状态检查面板整体消失，浏览器控制台零报错。

## Root Cause

宿主 @deepseek-ai/dsh-client-modules/lib/index.js 的 locatePkgJson/nearestPackage 要求 package.json 的 name 与 loader 行名严格相等才认领该包的 client 半身。别名安装让二者不相等：loader 行名 = dsh-our-free-model（插件自带 cordis.patch.yml 的 name），磁盘 package.json name = @ebony-vinyl/dsh-our-free-model。上溯找不到相符清单 → resolveMeta 返回 null → 该包被从 client 表删除 → client.js 不进 /plugins/?? 组合 → ctx.slots.inject('settings.section', …) 永不执行。全程静默无日志。

## Fix

改用 name 与 loader 行名一致的产物重装：下载仓库 Release 的 dsh-our-free-model-<版本>.tgz（用同目录 SHA256SUMS 校验），在应用内 设置→插件→添加插件→安装第三方插件 填入 tgz 绝对路径，装完立即启用，再完全退出重启 DSH。不要用 npm: 别名安装任何声明 dsh.client 的插件。

## Verification

抓 /plugins/?? 组合请求确认 <行名>/client.js 在内；重启后设置页出现该插件入口。
