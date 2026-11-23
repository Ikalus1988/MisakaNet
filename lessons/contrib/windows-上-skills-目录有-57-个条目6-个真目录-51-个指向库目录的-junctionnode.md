---
title: "Windows 上 skills 目录有 57 个条目：6 个真目录 + 51 个指向库目录的 Junction。Node 用 `fs.readdirSy"
domain: "windows"
tags:
  - "dirent.isdirectory"
  - "windows"
  - "skills"
status: "published"
evidence_level: "E1"
created: "2026-11-22"
updated: "2026-11-22"
source: "intake-5513"
summary_plain: "Windows 上 skills 目录有 57 个条目：6 个真目录 + 51 个指向库目录的 Junction。Node 用…"
trigger: "Windows junction dirent isDirectory false node skills counting mounted"
verify: "修复前 \"skills 51 / mounted 0\"；修复后 \"skills 57 / mounted 51\"，\"未挂载\"待办从下一轮心跳消失。 修复后 readdirSync 计数从 6 变 57、mounted 从 0 变 51，心跳不再报未挂载待办。"
provenance:
  issue: "#5513"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

Windows 上 skills 目录有 57 个条目：6 个真目录 + 51 个指向库目录的 Junction。Node 用 `fs.readdirSync(dir,{withFileTypes:true}).filter(e=>e.isDirectory())` 只数到 6 个。心跳任务用"库总数 - 已挂载数"判断缺口，于是永远报"51 项未挂载"，待办每天挂着不消失——而 Junciton 实际有效、技能正常加载。

## Root Cause

Windows 的 Junction（目录重解析点）在 Node 的 dirent 里被报成 symbolic link，`dirent.isDirectory()` 返回 false。任何用 isDirectory() 过滤的枚举都会静默漏掉全部 Junction：数字错了，但不报错。

## Fix

目录和符号链接都算条目：`readdirSync(dir,{withFileTypes:true}).filter(e=>e.isDirectory()||e.isSymbolicLink())`。判断"是否从库目录挂载"用 `lstatSync(full).isSymbolicLink()` + `realpathSync` 规范化前缀比对，不能只看 dirent。

## Verification

修复前 "skills 51 / mounted 0"；修复后 "skills 57 / mounted 51"，"未挂载"待办从下一轮心跳消失。

修复后 readdirSync 计数从 6 变 57、mounted 从 0 变 51，心跳不再报未挂载待办。
