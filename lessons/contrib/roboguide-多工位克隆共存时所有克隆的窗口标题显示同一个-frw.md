---
title: "ROBOGUIDE 多工位克隆共存时，所有克隆的窗口标题显示同一个 .frw 文件名（例如克隆自同一母壳的多个工位窗口标题逐字相同），按标题驱动的自动化（截图/"
domain: "mcp"
tags:
  - "roboguide"
  - "frw"
status: "published"
evidence_level: "E1"
created: "2026-11-25"
updated: "2026-11-25"
source: "intake-5787"
summary_plain: "ROBOGUIDE 多工位克隆共存时，所有克隆的窗口标题显示同一个 .frw 文件名（例如克隆自同一母壳的多个工位窗口标题逐字相同），按标题驱动的自动化（截图/定位子窗/连接控制器）会抓错工位；同一台机器上多份 services.txt…"
trigger: "ROBOGUIDE 工位 克隆 窗口标题 同名 .frw services.txt mtime 区分工位身份 标题不可信"
verify: "同机多克隆并存时窗口标题逐字相同（可现场复现）；活工位判据=该工位目录 Robot_1/services.txt mtime 最新且随引导重写；按三重证据选中的工位与引导对话框路径一致"
provenance:
  issue: "#5787"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

ROBOGUIDE 多工位克隆共存时，所有克隆的窗口标题显示同一个 .frw 文件名（例如克隆自同一母壳的多个工位窗口标题逐字相同），按标题驱动的自动化（截图/定位子窗/连接控制器）会抓错工位；同一台机器上多份 services.txt 端口表还都是克隆同值（web=9000 一片），按端口也认不出活的是谁。

## Root Cause

ROBOGUIDE 工位目录复制克隆时 .frw 文件名保持母壳不变，窗口标题取 .frw 名而非工位目录名；services.txt 是克隆时的静态快照，只有真正启动过的工位才会被重写。此前已有邻近教训（多工位克隆共用端口表导致清扫误杀）记录混乱后果，但「标题同名陷阱」本身没有判据化。

## Fix

识别当前活工位用三重证据：① 工位目录名（唯一可信身份）；② Robot_1/services.txt 的 mtime（哪个最新哪个就是最近引导的活控制器）；③ 进程命令行/引导对话框里的设备路径。自动化脚本里禁止把窗口标题当工位标识；对拍/采集前先打印三重证据确认身份再动手。

## Verification

同机多克隆并存时窗口标题逐字相同（可现场复现）；活工位判据=该工位目录 Robot_1/services.txt mtime 最新且随引导重写；按三重证据选中的工位与引导对话框路径一致
