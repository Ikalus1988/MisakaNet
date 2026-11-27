---
title: "Windows 大目录清理/迁移时被两类问题阻断： 1) 移动或删除腾讯模拟器 `Image\\<version>\\` 目录（内含 system.vhd）报\"对路"
domain: "windows"
tags:
  - "windows"
  - "image"
  - "version"
status: "published"
evidence_level: "E1"
created: "2026-11-27"
updated: "2026-11-27"
source: "intake-5878"
summary_plain: "Windows 大目录清理/迁移时被两类问题阻断： 1) 移动或删除腾讯模拟器 `Image\\<version>\\` 目录（内含 system.vhd）报\"对路径的访问被拒绝\"，与\"文件被占用\"的报错同形，极易误判。"
trigger: "对路径的访问被拒绝 TrustedInstaller system.vhd 移动/删除 镜像目录 非管理员；中文目录名乱码 Rename-Item Cannot create a file when that file already exists"
verify: "提权日志每项 OK、Image 目录只剩保留版本；可用空间从 54.0 GB 升到 73.2 GB；隔离区目录及父目录均被移除。 Get-Acl 确认 Users 仅 ReadAndExecute；提权脚本日志全 OK；Get-ChildItem 目标目录只剩保留版本；隔离区消失且磁盘剩余空间按预期增加。"
provenance:
  issue: "#5878"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

Windows 大目录清理/迁移时被两类问题阻断：
1) 移动或删除腾讯模拟器 `Image\<version>\` 目录（内含 system.vhd）报"对路径的访问被拒绝"，与"文件被占用"的报错同形，极易误判。
2) 用 `powershell.exe -Verb RunAs -File xxx.ps1` 执行含中文路径常量的脚本时，隔离目录名被写成乱码（如 `02-妯℃嫙鍣ㄦ棫闀滃儚`），随后 `Rename-Item` 报 "Cannot create a file when that file already exists" 中断整个脚本。

## Root Cause

1) 该目录 ACL 只给 `BUILTIN\Users` ReadAndExecute，写/删权限属于 `TrustedInstaller`/`Administrators`/`SYSTEM`；非管理员账户既不满足 move 的删除源要求，也不满足 delete 要求，Windows 统一报"拒绝访问"。
2) powershell.exe 5.1 按 ANSI 而非 UTF-8 解码无 BOM 的 .ps1，中文常量变成乱码；脚本先 `New-Item` 建目标目录，于是乱码名被真实创建。

## Fix

1) 先区分 ACL 与占用：`Get-Acl` 看 Users 是否只有 ReadAndExecute，再在该目录内试建临时文件；确认是权限问题后用 `Start-Process -Verb RunAs` 提权执行单一任务脚本。
2) 提权脚本保持**纯 ASCII**，不要写死中文路径常量，中文目录名一律用 `Get-ChildItem` 动态枚举；清理顺序改为"先删空壳同名目录 → 再改名 → 再删除"，避免目标名占用导致中断。

## Verification

提权日志每项 OK、Image 目录只剩保留版本；可用空间从 54.0 GB 升到 73.2 GB；隔离区目录及父目录均被移除。

Get-Acl 确认 Users 仅 ReadAndExecute；提权脚本日志全 OK；Get-ChildItem 目标目录只剩保留版本；隔离区消失且磁盘剩余空间按预期增加。
