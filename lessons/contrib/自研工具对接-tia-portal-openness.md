---
title: "自研工具对接 TIA Portal Openness API（Siemens.Engineering.dll）时连踩三个宿主/依赖坑，症状与修复如下（TIA P"
domain: "windows"
tags:
  - "tia"
  - "portal"
  - "openness"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4731"
summary_plain: "自研工具对接 TIA Portal Openness API（Siemens.Engineering.dll）时连踩三个宿主/依赖坑，症状与修复如下（TIA Portal V19，Windows PowerShell 5.1 /…"
trigger: "自研工具对接 TIA Portal Openness API（Siemens.Engineering.dll）时连踩三个宿主/依赖坑，症状与修复如下（TIA P. Portal V19，Windows PowerShell 5.1 / pwsh 7.7）。"
verify: "修复后：GetProcesses() 成功；TiaPortal(WithoutUserInterface) 建立会话直达 Openness 权限检查（证明 1)-3) 全部通过）；换入新令牌（重登或 runas 新会话）后可继续打开工程。同一根因与开源 tia-portal-mcp 社区此前记录的 \"PublicAPI 目录缺依赖\" 问题一致。"
provenance:
  issue: "#4731"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

自研工具对接 TIA Portal Openness API（Siemens.Engineering.dll）时连踩三个宿主/依赖坑，症状与修复如下（TIA Portal V19，Windows PowerShell 5.1 / pwsh 7.7）。

## Root Cause

1) **依赖目录错位**：`PublicAPI\V{n}` 目录只有 API 门面（Siemens.Engineering.dll），依赖 Siemens.Engineering.Contract.dll、Siemens.Engineering.ClientAdapter.Interfaces.dll 实际在 `Bin\PublicAPI`，不在 GAC。外部进程 LoadFrom 门面后调用即报 `Could not load file or assembly 'Siemens.Engineering.Contract ... Method does not exist (0x80131513)`。
2) **必须 .NET Framework 宿主**：Siemens.Engineering 是 .NET Framework 4.8 程序集且内部用 .NET Remoting。在 pwsh 7（.NET Core）里 new TiaPortal(...) 会报 `Could not load type 'System.Runtime.Remoting.Lifetime.ISponsor' from assembly 'mscorlib'`——Remoting 只存在于 Framework。
3) **PS 5.1 无泛型方法调用语法**：`$obj.GetService[T]()` 是 pwsh 7.4+ 语法，5.1 报 `Array index expression is missing or not valid`。
4) 附：Openness 组权限校验看**进程令牌**——把用户加进 "Siemens TIA Openness" 本地组后必须注销重登（新登录会话）才生效，报错文案为 `Owner '...' of this process is not member of the windows group 'Siemens TIA Openness'`。

## Fix

1) 注册 AssemblyResolve 把解析目录指向 `Bin\PublicAPI` 与 `PublicAPI\V{n}`（或把 Contract.dll、ClientAdapter.Interfaces.dll 复制进 PublicAPI\V{n}）。2) 用 powershell.exe 5.1 或 .NET FW 4.8 可执行文件做宿主（这正是主流 TIA MCP 桥接进程用 net48 的原因）。3) 泛型 GetService 用反射：GetMethod("GetService").MakeGenericMethod(type).Invoke(...)。4) 加组后重新登录再连。

## Verification

修复后：GetProcesses() 成功；TiaPortal(WithoutUserInterface) 建立会话直达 Openness 权限检查（证明 1)-3) 全部通过）；换入新令牌（重登或 runas 新会话）后可继续打开工程。同一根因与开源 tia-portal-mcp 社区此前记录的 "PublicAPI 目录缺依赖" 问题一致。
