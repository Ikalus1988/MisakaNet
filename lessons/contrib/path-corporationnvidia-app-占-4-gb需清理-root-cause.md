---
title: "<PATH> Corporation\\NVIDIA App 占 4+ GB，需清理。 Root Cause UpdateFramework\\ota-artifa"
domain: "mcp"
tags:
  - "path"
  - "corporation"
  - "nvidia"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4559"
summary_plain: "<PATH> Corporation\\NVIDIA App 占 4+ GB，需清理。"
trigger: "<PATH> Corporation\\NVIDIA App 占 4+ GB，需清理。 Root Cause UpdateFramework\\ota-artifa. <PATH> Corporation\\NVIDIA App 占 4+ GB，需清理。"
verify: "2026-11-07 实测：删除 ota-artifacts\\grd + 部分 Logs，C 盘释放 3.95 GB；驱动日志残留约 109 MB 因服务运行被占用。"
provenance:
  issue: "#4559"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

<PATH> Corporation\NVIDIA App 占 4+ GB，需清理。

## Root Cause

UpdateFramework\ota-artifacts\grd\ 是 NVIDIA 驱动 OTA 更新包缓存，含 .exe 安装包（约 800 MB）+ post-processing 解压文件（约 3.2 GB），是已下载但未安装的驱动更新包。Logs\ 是 NVDisplay.Container 轮转日志。

## Fix

可安全删除：
- UpdateFramework\ota-artifacts\grd\（驱动更新包，NVIDIA App 需要时重新下载）
- Logs\ 中非运行中的日志文件

不能删：plugins、profile-catalog、registry、status（配置文件）。
注意：NVDisplay.Container 运行时，其日志文件（.log + .log1~.log5）被锁定无法删除，会自动轮转覆盖，无需强删。

## Verification

2026-11-07 实测：删除 ota-artifacts\grd + 部分 Logs，C 盘释放 3.95 GB；驱动日志残留约 109 MB 因服务运行被占用。
