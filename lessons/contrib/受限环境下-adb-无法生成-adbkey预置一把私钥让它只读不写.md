---
title: "受限环境下 adb 无法生成 adbkey：预置一把私钥让它只读不写"
domain: "devops"
tags:
  - "windows"
  - "adb"
  - "android"
  - "permission"
  - "sandbox"
  - "crypto"
status: "published"
evidence_level: "E1"
created: "2026-11-08"
updated: "2026-11-08"
source: "intake-4450"
summary_plain: "在 Windows 上，从一个受限的父进程（宿主对子进程做了写入限制）调用 adb 时，设备永远停在 unauthorized。adb 日志：auth.cpp:84 Failed to open…"
trigger: "受限环境下 adb 无法生成 adbkey：预置一把私钥让它只读不写. 在 Windows 上，从一个受限的父进程（宿主对子进程做了写入限制）调用 adb 时，设备永远停在 unauthorized。adb 日志：auth.cpp:84…"
verify: "adb devices 由 unauthorized 变为 device；adb shell getprop ro.product.model 有返回；adb shell screencap -p <PATH> 配合 adb pull 能拿到非空图片。"
provenance:
  issue: "#4450"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

在 Windows 上，从一个受限的父进程（宿主对子进程做了写入限制）调用 adb 时，设备永远停在 unauthorized。adb 日志：auth.cpp:84 Failed to open <PATH><user>\.android\adbkey: Permission denied → Failed to generate new key → Failed to get user public key。同样这个路径，用交互式 PowerShell 建文件完全正常。另有 adb 守护进程写不了 %TEMP%\adb.log（cannot open ...: Permission denied），直接 failed to start daemon。

## Root Cause

两个机制叠在一起：(1) adb 在 Windows 上把用户密钥路径硬编码为 %USERPROFILE%\.android\adbkey，实测改 USERPROFILE / ANDROID_USER_HOME / HOME 都不改变它去找的位置；(2) 写入限制只作用于子进程，交互式 shell 不在同一限制内，所以"PowerShell 能写、adb 不能写"并不矛盾。adb 拿不到私钥时会尝试现场生成，生成失败就没有公钥可发给设备，授权流程永远走不完。

## Fix

1) 用 .NET 生成 PKCS#8 RSA-2048 私钥，直接写到 adb 期望的位置（这一步用有权限的进程做）：先建目录，再 $rsa=[System.Security.Cryptography.RSA]::Create(2048); Set-Content -LiteralPath "$env:USERPROFILE\.android\adbkey" -Value $rsa.ExportPkcs8PrivateKeyPem() -Encoding ascii -NoNewline。2) 把 TMP/TEMP 指到一个可写目录，让 adb 守护进程能写日志并启动。3) adb kill-server 后重连，设备上点允许。

## Verification

adb devices 由 unauthorized 变为 device；adb shell getprop ro.product.model 有返回；adb shell screencap -p <PATH> 配合 adb pull 能拿到非空图片。
