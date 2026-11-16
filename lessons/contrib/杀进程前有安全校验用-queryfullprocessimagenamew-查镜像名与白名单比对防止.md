---
title: "杀进程前有安全校验：用 QueryFullProcessImageNameW 查镜像名与白名单比对，防止 services.txt 账本里的旧 pid 被系统复"
domain: "windows"
tags:
  - "queryfullprocessimagenamew"
  - "services"
  - "txt"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-5023"
summary_plain: "杀进程前有安全校验：用 QueryFullProcessImageNameW 查镜像名与白名单比对，防止 services.txt 账本里的旧 pid 被系统复用后误杀无辜进程。但对 COM 起的宿主进程（镜像名以 -Embedding…"
trigger: "杀进程前有安全校验：用 QueryFullProcessImageNameW 查镜像名与白名单比对，防止 services.txt 账本里的旧 pid 被系统复. 被系统复用后误杀无辜进程。但对 COM 起的宿主进程（镜像名以 -Embedding 启动）取名返回 None，被当成「pid 已被复用」直接跳过杀进程…"
verify: "离线自测覆盖：短名族匹配 4 例（含「fr.exe 不许命中 frrobot 族」反例）、WMI 兜底对本进程取名成功、三态判定对本进程返回「不符」而非「未知」；修复后现场清场不再漏杀 COM 僵尸，双实例互堵消失。 自测 7/7（短名族 4 例含反例、WMI 兜底、三态判定）；现场 COM 僵尸不再漏杀"
provenance:
  issue: "#5023"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

杀进程前有安全校验：用 QueryFullProcessImageNameW 查镜像名与白名单比对，防止 services.txt 账本里的旧 pid 被系统复用后误杀无辜进程。但对 COM 起的宿主进程（镜像名以 -Embedding 启动）取名返回 None，被当成「pid 已被复用」直接跳过杀进程 → 该清的僵尸实例清不掉 → 双实例互堵、互报「正在被其他进程使用」，表象是「启动卡死」。

## Root Cause

1. 把「身份查询失败」误当成「身份不符」：单点查询 API（OpenProcess/QueryFullProcessImageNameW）对受限/COM 托管进程会拒绝，失败原因是权限/托管方式，不是 pid 复用；
2. 白名单精确匹配放不过 8.3 短名（FRVIRT~1.EXE、FRROBO~1.EXE 这类被宿主以短路径拉起的进程名），同族进程被误判为「不符」。

## Fix

1. 身份判定拆三态：匹配 / 不符（真复用）/ 未知（查询失败），「未知」如实报告，不冒充「不符」；
2. 查询两级兜底：Win32 API 失败后按**进程名族**兜底查 WMI 进程名（Win32_Process.Name，不要求 OpenProcess 权限）；
3. 8.3 短名按 `~` 截断做前缀族匹配（frrobo~1 → frrobot 族），但前缀匹配只对含 `~` 的短名开闸，防止无关短名蒙混；
4. 扫描清场名单同样按名族收口（否则僵尸进程名是短名时扫描也漏）。

## Verification

离线自测覆盖：短名族匹配 4 例（含「fr.exe 不许命中 frrobot 族」反例）、WMI 兜底对本进程取名成功、三态判定对本进程返回「不符」而非「未知」；修复后现场清场不再漏杀 COM 僵尸，双实例互堵消失。

自测 7/7（短名族 4 例含反例、WMI 兜底、三态判定）；现场 COM 僵尸不再漏杀
