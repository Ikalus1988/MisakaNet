---
title: "用 tia-portal-mcp 1.1.0 连本机 TIA Portal V16（装在 <PATH> V16，不在 C 盘）时依次卡三处： 1. connec"
domain: "windows"
tags:
  - "tia"
  - "portal"
  - "mcp"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4368"
summary_plain: "用 tia-portal-mcp 1.1.0 连本机 TIA Portal V16（装在 <PATH> V16，不在 C 盘）时依次卡三处： 1."
trigger: "用 tia-portal-mcp 1.1.0 连本机 TIA Portal V16（装在 <PATH> V16，不在 C 盘）时依次卡三处： 1. connec. 用 tia-portal-mcp 1.1.0 连本机 TIA Portal V16（装在 <PATH> V16，不在 C 盘）时依次卡三处： 1."
verify: "`connect_tia(version=\"16.0\", portal_mode=\"any-ui\")` 返回 `connected: true`，带 `project`（实测 项目10）与 `plcs: [{name: PLC_1, online_state: Offline}]`；`get_plc_inventory` 能列出 `Main` 块。预检脚本（检查主实例数、两项注册表、5 个…"
provenance:
  issue: "#4368"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

用 tia-portal-mcp 1.1.0 连本机 TIA Portal V16（装在 <PATH> V16，不在 C 盘）时依次卡三处：

1. connect_tia 报 `OpennessAccessException: No matching TIA Portal version could be found.` —— 注册表 `HKLM\SOFTWARE\Siemens\Automation\Openness` 键存在但完全为空，无子键无值。
2. 补齐注册表后变成 `TypeInitializationException: "Siemens.Engineering.TiaPortal"的类型初始值设定项引发异常`。
3. 由 agent 后台启动 TIA 时弹「该应用程序无法启动。<PATH><user>\AppData\Roaming\Siemens\Automation\Portal V16\Settings\Settings.xml 写保护。请联系您的系统管理员。」，或几个实例一起卡在 `Siemens` 启动画面、托盘冒红点。

## Root Cause

1) Openness 注册表未登记：缺 `Openness\16.0` 下的 `InstallDir`，也缺 `Openness\16.0\PublicAPI\16.0` 下的 `Siemens.Engineering`。

2) `TypeInitializationException` 只是外壳，内层真实异常是 `System.IO.FileLoadException: Cannot load assembly. Check your openness environment or contact your administrator.` 堆栈在 `Siemens.Engineering.Private.LocationProvider.Validation()` 与 `Siemens.Engineering.TiaPortal..cctor()`。原因是 MCP 的 `_internal\` 自带的 Siemens 程序集与 TIA 安装目录 `PublicAPI\V16\` 的同名 DLL 字节不同（`Siemens.Engineering.dll` 1336832 vs 1281536 字节；`Siemens.Automation.Opns.ObjectModel.Impl.dll` 3971072 vs 3936256），两边 `FileVersion` 都写 `1600.0.3102.1`，光看版本号看不出来。西门子按文件内容做完整性校验，不看路径也不看版本号。

3) Settings.xml 写保护不是 NTFS 权限问题：该文件 Attributes=Archive、ACL 有 FullControl、`[System.IO.File]::Open($f,'Open','ReadWrite','None')` 能独占打开成功。真因是 agent 托管子进程（沙箱/作业对象）叠加已有 TIA 实例，导致新实例初始化失败。

## Fix

1) 管理员权限写两项注册表：`Openness\16.0` → `InstallDir = <PATH> V16`；`Openness\16.0\PublicAPI\16.0` → `Siemens.Engineering = <PATH> V16\PublicAPI\V16\Siemens.Engineering.dll`。

2) 停掉 MCP，备份后把安装目录 `PublicAPI\V16` 的 5 个文件覆盖到 `_internal`：`Siemens.Engineering.dll`、`Siemens.Engineering.Contract.dll`、`Siemens.Engineering.ClientAdapter.Interfaces.dll`、`Siemens.Engineering.Hmi.dll`、`Siemens.Automation.Opns.ObjectModel.Impl.dll`，再启动 MCP。MCP 必须从 Openness 白名单登记的路径启动（`Openness\16.0\Whitelist\tia-portal-mcp.exe\Entry` 的 Path/DateModified/FileHash 三项全匹配），换路径会崩 `0xE0434352` 或报「未发现可附加的 TIA Portal V16 实例」。

3) TIA 由用户手动双击 `Bin\Siemens.Automation.Portal.exe` 启动，不要从 agent 后台拉；有残留实例先全杀再开一个。命令行带 `-Name=SearchReplaceBackgroundProcess` 的是后台子进程，不算第二个实例。

4) 排查提速：用 Windows PowerShell 5.1（.NET Framework，不是 pwsh 7）加载指定目录的 `Siemens.Engineering.dll` 并调 `TiaPortal.GetProcesses()`，能把内层异常链打出来；同样的探针在 pwsh 7 下复现不出来。

## Verification

`connect_tia(version="16.0", portal_mode="any-ui")` 返回 `connected: true`，带 `project`（实测 项目10）与 `plcs: [{name: PLC_1, online_state: Offline}]`；`get_plc_inventory` 能列出 `Main` 块。预检脚本（检查主实例数、两项注册表、5 个 DLL 的 SHA256、8000 端口）输出 `problems: 0`、退出码 0。
