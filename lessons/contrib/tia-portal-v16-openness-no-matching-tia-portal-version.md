---
title: "TIA Portal V16 Openness 连接报 No matching TIA Portal version 与 GetPlcs 报 not supported in this API version"
domain: "automation"
tags:
  - "tia"
  - "portal"
  - "openness"
  - "v16"
  - "il"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-3572"
summary_plain: "用 tia-portal-mcp 1.1.0 连接本机 TIA Portal V16 时，connect_tia 一直返回 OpennessAccessException: No matching TIA Portal version…"
trigger: "TIA Portal V16 Openness 连接报 No matching TIA Portal version 与 GetPlcs 报 not supported in this API version. 用 tia-portal-mcp 1.1.0 连接本机 TIA Portal V16…"
verify: "connect_tia(version=16.0, portal_mode=any-ui) 返回 connected:true 并能读到工程名与 PLC 列表；get_plcs 不再报错；TIA 侧出现 Openness 安全确认对话框时需点允许。"
provenance:
  issue: "#3572"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

用 tia-portal-mcp 1.1.0 连接本机 TIA Portal V16 时，connect_tia 一直返回 OpennessAccessException: No matching TIA Portal version could be found.；按注册表补齐能连上后，get_plcs 又报 OpennessAccessException: The method is not supported in this API version.

## Root Cause

两处独立问题：(1) OpennessAdapter 1.4.3 的 GetOpennessLibraries 从 HKLM\SOFTWARE\Siemens\Automation\Openness\<版本>\PublicAPI\<apiVer> 读取值 Siemens.Engineering 定位 API dll；本机 Openness\16.0 下只有 InstallDir、没有 PublicAPI 子键，AvailablePortals 因此为 0，且 PublicAPI\V16 目录本身缺少 Siemens.Engineering.Contract 等依赖。(2) tia-portal-mcp 1.1.0 的 OpennessApi16.dll 里 DownloadConfig.SetDefaultConfig 无条件调用 SetDataBlockReinitializationSelection，而该方法在 V16 包装 DLL 中直接 throw NotSupportedException；Project.GetPlcs 构造 Plc 对象时会 new DownloadConfig 并调用 SetDefaultConfig，于是整个 GetPlcs 失败。

## Fix

1) 管理员权限写注册表：HKLM\SOFTWARE\Siemens\Automation\Openness\16.0\PublicAPI\16.0 下值 Siemens.Engineering = <TIA安装目录>\PublicAPI\V16\Siemens.Engineering.dll；同时把 Bin\PublicAPI 的 Siemens.Engineering.Contract.dll、Siemens.Engineering.ClientAdapter.Interfaces.dll 与 Bin\PublicAPI\V16\Siemens.Automation.Opns.ObjectModel.Impl.dll 复制到 PublicAPI\V16。2) 对 MCP 的 _internal\Siemens.TiaPortal.OpennessApi16.dll 做 IL 补丁：方法 SetDataBlockReinitializationSelection 的 tiny header 0x2E 改 0x06、IL 首字节 0x72(ldstr) 改 0x2A(ret)（该版本 RVA 0xDD01、文件偏移 0xBF01），改前备份 .bak。3) 重启 MCP 服务进程后重连。

## Verification

connect_tia(version=16.0, portal_mode=any-ui) 返回 connected:true 并能读到工程名与 PLC 列表；get_plcs 不再报错；TIA 侧出现 Openness 安全确认对话框时需点允许。
