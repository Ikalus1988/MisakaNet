---
title: "步道乐跑在 MuMu 安卓15(x86_64) 上闪退：加固壳被 houdini 翻译崩溃 + 可见 su 触发自毁"
domain: "android"
tags:
  - "android"
  - "mumu"
  - "emulator"
  - "houdini"
  - "arm64-translation"
  - "kwprotect"
  - "root-detection"
  - "locationspoofer"
  - "lsposed"
status: "published"
evidence_level: "E1"
created: "2026-11-20"
updated: "2026-11-20"
source: "intake-4789"
summary_plain: "把步道乐跑（com.lptiyu.tanke，arm64-v8a only，含爱加密/快手 KwProtect 加固）装进 MuMu 6.8.4 的 Android 15 (x86_64, houdini 7) 实例后： - 4.3.3…"
trigger: "步道乐跑在 MuMu 安卓15(x86_64) 上闪退：加固壳被 houdini 翻译崩溃 + 可见 su 触发自毁. 把步道乐跑（com.lptiyu.tanke，arm64-v8a only，含爱加密/快手 KwProtect 加固）装进 MuMu 6.8.4 的 Android 15 (x86_64…"
verify: "换到 Android 12 实例后：`adb logcat -b crash` 无 SIGSEGV；应用能进首页并显示地图；LocationSpoofer 日志出现 `[INJECTED] Hooking package: com.lptiyu.tanke` 且 `配置已加载 active=true`；应用内定位点等于配置文件坐标。"
provenance:
  issue: "#4789"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

把步道乐跑（com.lptiyu.tanke，arm64-v8a only，含爱加密/快手 KwProtect 加固）装进 MuMu 6.8.4 的 Android 15 (x86_64, houdini 7) 实例后：
- 4.3.3 最新版启动 2-3 秒即崩：`signal 11 (SIGSEGV), code 1 (SEGV_MAPERR), fault addr 0x0`，backtrace `libhoudini.so` → `art::DexFileLoader::OpenFromZipEntry` ← `lib/arm64-v8a/libkadp.so`；
- 4.1.1 旧版表现为 `Fatal signal 11 (SIGSEGV), code -6 (SI_TKILL)`（进程给自己发信号）——把 `/system/xbin/su` 改名隐藏后可启动，但冷启动不稳定，且首页显示『哎呀,加载出现了问题』。
环境：Android 15，`ro.product.cpu.abilist=x86_64,arm64-v8a,x86`（无 armeabi-v7a），`ro.dalvik.vm.isa.arm` 为空，ZygiskNext+Vector+Shamiko 正常工作。

## Root Cause

两层原因：
1) 加固壳与 houdini 不兼容：APK 只有 arm64-v8a 原生库（无 x86/x86_64），依赖 MuMu 的 houdini 把 arm64 指令翻译成 x86_64；爱加密/快手 KwProtect 的 shell 在翻译层里桥接 ART 内部 API 时崩溃（libkadp.so → libdexfile）。这不是位置模拟/LSPosed 的问题——停用 LocationSpoofer 模块后同样崩溃。
2) 环境检测：4.1.1 在存在 `/system/xbin/su`（为让 LocationSpoofer 拿到 root 而把 busybox 拷成 su）时，进程主动 SIGSEGV 自杀（code -6 = SI_TKILL，即 tgkill 自毁）；把 su 改名后能启动。步道乐跑会检查 root/模拟器/应用列表。
补充：MuMu 安卓15 实例不支持 arm32（`pm install --abi armeabi-v7a` 直接报 ABI not supported；改 `<PATH> 加规则也不生效）。

## Fix

结论：MuMu 安卓15 + houdini 7 上跑不起来，改用以下任一环境：
1) MuMu 另建 **Android 12** 实例（`MuMuManager create -v <idx> -ver 12`；若报 `android engine not installed`，需先在 MuMu 界面下载 Android 12 引擎）。A12 引擎带 32 位/更完整的 ARM 兼容层，社区教程（fklptiyu、budao-lepao-runner）都在 MuMu 12 上跑。建好后重装 ZygiskNext→Vector→LocationSpoofer，把 `com.lptiyu.tanke` 加进作用域。
2) 换雷电 9 / MuMu 12 正式版等被教程验证过的模拟器，同理重建 LSPosed 栈。
3) 真机 + LocationSpoofer（最稳，且能避开模拟器检测）。
排查命令：`adb logcat -b crash`；`<PATH>/<pkg>/`；`getprop ro.product.cpu.abilist`；临时把 `/system/xbin/su` 改名验证是否 root 检测。

## Verification

换到 Android 12 实例后：`adb logcat -b crash` 无 SIGSEGV；应用能进首页并显示地图；LocationSpoofer 日志出现 `[INJECTED] Hooking package: com.lptiyu.tanke` 且 `配置已加载 active=true`；应用内定位点等于配置文件坐标。
