---
title: "桌面应用遥测出现「混血」事件：同一设备的部分事件带新契约的 UUID v4 幂等键，但 data.version 停在旧版号（如 6.20.0），版本维度因此不"
domain: "mcp"
tags:
  - "beforebuildcommand"
  - "cargo"
  - "tauri"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4788"
summary_plain: "桌面应用遥测出现「混血」事件：同一设备的部分事件带新契约的 UUID v4 幂等键，但 data.version 停在旧版号（如 6.20.0），版本维度因此不可信。二进制 strings 扫描旧版号 0…"
trigger: "桌面应用遥测出现「混血」事件：同一设备的部分事件带新契约的 UUID v4 幂等键，但 data.version 停在旧版号（如 6.20.0），版本维度因此不. 版本维度因此不可信。二进制 strings 扫描旧版号 0 命中，被误判为「版本是运行时读取」。"
verify: "①三元组逐副本实测（FileVersion × 窗口显示版本 × 新功能入口）——混血格=FileVersion 新+显示版本旧，现存副本全自洽则来源副本已消失；②每副本触发同名事件对号（报文 UUID 形态+版本+时刻）5/5 吻合；③机制复核：报文 version=前端 define、幂等键=入队时铸造，同进程必同源。可泛化：一切「构建期元数据 + 分层构建管线」（前端 define /…"
provenance:
  issue: "#4788"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

桌面应用遥测出现「混血」事件：同一设备的部分事件带新契约的 UUID v4 幂等键，但 data.version 停在旧版号（如 6.20.0），版本维度因此不可信。二进制 strings 扫描旧版号 0 命中，被误判为「版本是运行时读取」。

## Root Cause

版本是**构建期常量**（前端打包 define 从 package.json 焊进 bundle），但分层构建管线里 `cargo build` 不走 Tauri 的 `beforeBuildCommand`（不重编前端）——沿用磁盘上的旧 dist，产出「新 Rust（新幂等键逻辑）+ 旧前端（旧版本常量）」的混血二进制；本地开发构建被当发布件跑了。strings 扫不到不是「运行时来源」的证据：前端资产压缩嵌入，裸扫描看不见字面量。

## Fix

本地构建统一走 `tauri build`（或 cargo 前先 `npm run build`）；发布链本来就现编前端所以正式发版件一直是安全的。诊断时把「版本注入点」追到构建期 define/build.rs/版本资源，别信裸 strings 的缺席。

## Verification

①三元组逐副本实测（FileVersion × 窗口显示版本 × 新功能入口）——混血格=FileVersion 新+显示版本旧，现存副本全自洽则来源副本已消失；②每副本触发同名事件对号（报文 UUID 形态+版本+时刻）5/5 吻合；③机制复核：报文 version=前端 define、幂等键=入队时铸造，同进程必同源。可泛化：一切「构建期元数据 + 分层构建管线」（前端 define / build.rs / PE 版本资源不同步）都可能造出混血二进制。
