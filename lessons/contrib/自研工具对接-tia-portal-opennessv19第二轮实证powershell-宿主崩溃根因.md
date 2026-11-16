---
title: "自研工具对接 TIA Portal Openness（V19）第二轮实证：PowerShell 宿主崩溃根因 + 归档/工程两类 API 正确用法 + 检索 P"
domain: "windows"
tags:
  - "new"
  - "tia"
  - "portal"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4736"
summary_plain: "自研工具对接 TIA Portal Openness（V19）第二轮实证：PowerShell 宿主崩溃根因 + 归档/工程两类 API 正确用法 + 检索 PlcSoftware 的官方路径。"
trigger: "自研工具对接 TIA Portal Openness（V19）第二轮实证：PowerShell 宿主崩溃根因 + 归档/工程两类 API 正确用法 + 检索 P. PlcSoftware 的官方路径。"
verify: "MICAR 模板全链路跑通（2026-11-12）：runas 令牌带 Siemens TIA Openness 组 → TiaPortal(WithoutUserInterface) session OK → Retrieve 解开 677MB .zap19 → 工程名 MICAR2.0_PLC_Template → 枚举 7 设备（PLC_Templates_V1.6：830 块/3…"
provenance:
  issue: "#4736"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

自研工具对接 TIA Portal Openness（V19）第二轮实证：PowerShell 宿主崩溃根因 + 归档/工程两类 API 正确用法 + 检索 PlcSoftware 的官方路径。

## Root Cause

1) **PowerShell 承载 TiaPortal 必栈溢出**：pwsh7 与 powershell 5.1 在 `new TiaPortal(...)` 返回时均 `Process is terminated due to StackOverflowException`（进程直接死亡、异常不可捕获、报告无法落盘）。根因是 PS 的 PSObject 适配器对 TiaPortal 的 .NET Remoting 代理递归包装。换成 .NET FW 4.8 控制台 exe（csc 直编）后同一调用抛出的是正常可捕获的 `EngineeringSecurityException`。结论：**Openness 桥接进程必须是 net48 可执行文件，PowerShell 只能做外围**（与主流开源 TIA MCP 的双进程/独立 exe 设计一致）。
2) **`.zap` 归档不能用 Open 打开**：`ProjectComposition.Open(FileInfo)` 只接受 `.ap` 工程；传 `.zap19` 报 "Unable to open the project…指定的路径无效"。API 里另有 **`Retrieve(FileInfo archive, DirectoryInfo targetDir)`**（及 RetrieveWithUpgrade/ProjectOpenMode 重载）专用于归档：解包到目标目录并打开工程。归档本体是标准 ZIP（PK 头）。
3) **PlcSoftware 检索路径**：`DeviceItem.GetService<PlcSoftware>()` 编译失败（PlcSoftware 不实现 IEngineeringService）。正确链路：`GetService<Siemens.Engineering.HW.Features.SoftwareContainer>()` → `.Software as PlcSoftware`。块枚举在 **`sw.BlockGroup.Blocks`**（+ `Groups` 递归），不是 `sw.Blocks`（不存在）；标签表 `sw.TagTableGroup.TagTables`。`Projects.Open` 的参数是 `FileInfo` 不是 string。

## Fix

1) 用 csc 编译 net48 exe 承载 Openness（源码存 UTF-8 BOM，否则 csc 按 GBK 误读非 ASCII 字面量；或 \u 转义）。2) 归档用 `Projects.Retrieve(new FileInfo(zap), new DirectoryInfo(目标空目录))`；工程文件才用 `Open(new FileInfo(ap))`。3) 按 SoftwareContainer→Software→PlcSoftware→BlockGroup.Blocks 链路枚举。4) 提权/组令牌场景用 `runas /user:...` 铸新登录会话（组权限进令牌），无需注销。

## Verification

MICAR 模板全链路跑通（2026-11-12）：runas 令牌带 Siemens TIA Openness 组 → TiaPortal(WithoutUserInterface) session OK → Retrieve 解开 677MB .zap19 → 工程名 MICAR2.0_PLC_Template → 枚举 7 设备（PLC_Templates_V1.6：830 块/3 标签表/76 标签；++010HMI01；SINAMICS G_1；Measuring device×3）。同一调用序列在 PS 宿主下必 SO，在 exe 宿主下稳定。
