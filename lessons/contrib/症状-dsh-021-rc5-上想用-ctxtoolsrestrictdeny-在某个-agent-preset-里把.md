---
title: "DSH preset 里 tools.restrict 一次摘 41 个 MCP 工具：全部失败"
domain: "windows"
tags:
  - "dsh"
  - "rc"
  - "ctx"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4477"
summary_plain: "DSH preset 里 tools.restrict 一次摘 41 个 MCP 工具：全部失败"
trigger: "DSH preset 里 tools.restrict 一次摘 41 个 MCP 工具：全部失败"
verify: "在一次性 profile 里真启动，看 stderr 里守卫自己打印的收敛行： ```powershell # 隔离副本（node_modules 用 junction，不复制），改 patch 后真启动 & dsh.cmd --profile ctxtest --no-open --port 4399 2> $env:TEMP\\t.err Select-String…"
provenance:
  issue: "#4477"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

DSH 0.2.1-rc.5 上想用 `ctx.tools.restrict({deny:[...]})` 在某个 agent preset 里把 41 个 MCP 工具（`mcp__snowluma__*`）从模型工具列表里摘掉以省上下文。在 preset 的插件 `apply()` 里一次性调用，结果 **41 个全部失败**，一行没生效；同时观察到 `tools/change` 会风暴式触发。

## Root Cause

两层叠加：

1. **apply() 时机太早。** preset 插件 apply 的那一刻，全局工具层里只有 7 个工具（`list_mcp_resources` 等宿主工具），MCP 子进程还没连上来。`restrict()` 对"当前未知的名字"是**整批原子抛错**：
   `tools.restrict() names unknown global tool "mcp__snowluma__qq_add_sticker"; known global tools: ...`
   （源码：`dsh-tools/lib/index.js` 的 `restrict(filter)` 先取 `this.view(scope).restrictableNames`，再对 `allow`/`deny` 求差集，unknown 非空即 throw。）

2. **改成监听 `tools/change` + 退避重试后，只从 0/41 爬到 3/41 就卡死。** 日志显示同为 MCP 的 `mcp__douyin-web__*` 确实出现在 known global tools 里，但 `mcp__snowluma__*` 始终不在 —— 说明不是"MCP 工具都不在全局层"，而是这个 server 的工具注册路径/时机与别的 server 不同。同时每次 restrict 成功都再触发一次 `tools/change`，形成事件风暴（实测一晚上刷出几百行日志，每轮几十次异常构造）。

## Fix

1. **别在 preset 的 `apply()` 里一次性 restrict 全局工具。** 需要跟随工具集变化：监听 `tools/change` 事件 + 退避定时器（1/2/4/8/15s）多轮补藏，成功过的名字进 done 集合不再重试（单调收敛，避免自我触发的死循环）。
2. **先量收益再动手。** 本次目标是省工具定义字符：46 个工具共 29,206 字符，压描述的天花板实测只有 768 字符（≈192 token/轮），而"摘掉整批工具"才 29,206——但后者在当前版本不可达。
3. **`--dump-config` 通过不等于插件能激活。** 必须真启动验证（见 Verification）。

## Verification

在一次性 profile 里真启动，看 stderr 里守卫自己打印的收敛行：

```powershell
# 隔离副本（node_modules 用 junction，不复制），改 patch 后真启动
& dsh.cmd --profile ctxtest --no-open --port 4399 2> $env:TEMP\t.err
Select-String $env:TEMP\t.err -Pattern 'restrict'
```

判据：出现 `ok=<总数>/<总数>` 才算成功；出现 `ok=3/41` 这种"爬不动"说明该 server 的工具不参与 restrict。

一次性 profile 真启动，stderr 里守卫自报 ok=N/N 才算成功；ok=3/41 表示该 MCP server 的工具不参与 restrict。
