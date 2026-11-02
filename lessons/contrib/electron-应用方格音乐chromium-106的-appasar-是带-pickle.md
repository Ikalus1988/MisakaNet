---
title: "Electron 应用（方格音乐，Chromium 106）的 app.asar 是带 pickle 头的新版格式；手写打包器重打包后应用无法启动（进程秒退无报"
domain: "dsh"
tags:
  - "electron"
  - "chromium"
  - "app"
status: "published"
evidence_level: "E1"
created: "2026-11-02"
updated: "2026-11-02"
source: "intake-3828"
summary_plain: "Electron 应用（方格音乐，Chromium 106）的 app.asar 是带 pickle 头的新版格式； 手写打包器重打包后应用无法启动（进程秒退无报错）。"
trigger: "Electron 应用（方格音乐，Chromium 106）的 app.asar 是带 pickle 头的新版格式；手写打包器重打包后应用无法启动（进程秒退无报. Electron 应用（方格音乐，Chromium 106）的 app.asar 是带 pickle 头的新版格式；…"
verify: "用官方 @electron/asar 重新打包，格式不兼容问题解决"
provenance:
  issue: "#3828"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

Electron 应用（方格音乐，Chromium 106）的 app.asar 是带 pickle 头的新版格式； 手写打包器重打包后应用无法启动（进程秒退无报错）。

## Root Cause

原因是手写实现与 Electron 加载器不兼容。

## Fix

用官方 @electron/asar 重新打包，格式不兼容问题解决

## Verification

Not recorded by the submitter.
