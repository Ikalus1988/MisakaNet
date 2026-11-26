---
title: "一个调度插件用 POST /run {\"dryRun\":true} 触发\"只看不发\"的手动预览，结果邮件真的发出去了。 Root Cause 编排函数先算出 c"
domain: "dsh"
tags:
  - "cfg"
  - "post"
  - "run"
status: "published"
evidence_level: "E1"
created: "2026-11-26"
updated: "2026-11-26"
source: "intake-5838"
summary_plain: "一个调度插件用 POST /run {\"dryRun\":true} 触发\"只看不发\"的手动预览，结果邮件真的发出去了。"
trigger: "dryRun 手动预览仍然发了邮件 / dryRun flag ignored / generated.config overwrite"
verify: "补一条纯函数单测：generated.dryRun=false + dryRun=true → true；dryRun 未传 → 保持 false；配置里 dryRun=true 且调用方未要求 → 仍 true。再真机 POST {\"dryRun\":true} 复核响应里 mailed=false。 POST /run {\"dryRun\":true} 后响应 mailed=false…"
provenance:
  issue: "#5838"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

一个调度插件用 POST /run {"dryRun":true} 触发"只看不发"的手动预览，结果邮件真的发出去了。

## Root Cause

编排函数先算出 cfg = {...refreshConfig(), dryRun:true}，随后调用内部的 generate()；generate() 自己又执行了一次 refreshConfig() 并把那份配置作为返回值的一部分返回，调用方直接 `cfg = generated.config` 覆盖掉手动 dryRun。发信判断读的是 cfg.dryRun，于是变回 false。

## Fix

把「调用方意图」与「配置返回值」的合并抽成纯函数，并规定开关只允许单向收紧：dryRun !== true 时用生成的配置，否则强制 { ...generated, dryRun: true }。发信分支只读这个合并后的值。

## Verification

补一条纯函数单测：generated.dryRun=false + dryRun=true → true；dryRun 未传 → 保持 false；配置里 dryRun=true 且调用方未要求 → 仍 true。再真机 POST {"dryRun":true} 复核响应里 mailed=false。

POST /run {"dryRun":true} 后响应 mailed=false 且收件箱无新邮件；单测断言 resolveRunConfig(gen.dryRun=false, true).dryRun === true
