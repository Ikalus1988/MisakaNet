---
title: "Shamiko 在 MuMu 模拟器的 KernelSU 上拒装（KernelSU version abnormal）的手工安装解法"
domain: "android"
tags:
  - "mumu"
  - "kernelsu"
  - "shamiko"
  - "magisk"
  - "module-install"
  - "zstd"
  - "emulator"
  - "android15"
  - "root-hiding"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-3176"
summary_plain: "在 MuMu 6.8.4（Android 15）里用 KernelSU 的模块安装器装 Shamiko v1.2.5 会失败： adb push Shamiko-v1.2.5-414-release.zip…"
trigger: "Shamiko 在 MuMu 模拟器的 KernelSU 上拒装（KernelSU version abnormal）的手工安装解法. 在 MuMu 6.8.4（Android 15）里用 KernelSU 的模块安装器装 Shamiko v1.2.5 会失败： adb push…"
verify: "adb shell \"/system/xbin/dusk module list\" # id=zygisk_shamiko, enabled=true adb shell \"ls /data/adb/zygisksu/\" # 出现 no_mount_znctl（Shamiko 的 post-fs-data.sh 跑过的证据） adb shell \"ls…"
public_analogue: "busybox"
provenance:
  issue: "#3176"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

在 MuMu 6.8.4（Android 15）里用 KernelSU 的模块安装器装 Shamiko v1.2.5 会失败：
  adb push Shamiko-v1.2.5-414-release.zip /data/local/tmp/shamiko.zip
  adb shell "/system/xbin/dusk module install /data/local/tmp/shamiko.zip"
输出：
- Installing to /data/adb/modules_update/zygisk_shamiko
- Extracting module files / - Running module installer
- Device is system-as-root
- KernelSU version: 32525 (kernel) + 32525 (ksud)
*********************************************************
! KernelSU version abnormal!
! Please integrate KernelSU into your kernel as submodule instead of copying the source code
*********************************************************
- Error: Failed to install module script
（MuMu 的 KernelSU CLI 被改名成 /system/xbin/dusk，本质是 ksud 3.2.5 / versionCode 32525；注意装模块前必须先 adb root，否则报 Error: Permission denied (os error 13)。）

## Root Cause

Shamiko 的 customize.sh 会校验内核里的 KernelSU 版本字符串格式。MuMu 用的是被网易魔改、以复制源码方式集成的 KernelSU，版本串只是一个裸数字 32525，Shamiko 把它判定为“非子模块集成”的异常版本并直接 abort；因此失败发生在 Running module installer 阶段，与 ZygiskNext/Vector 无关。

## Fix

绕开安装器，手工把模块文件铺进模块目录：
1) 本机解包（zip 内 module.prop 等是 zstd 压缩，Python zipfile 会报 NotImplementedError: That compression method is not supported；用 Windows 自带 bsdtar 即可）：
   mkdir C:\Temp\shamiko ; tar.exe -xf Shamiko-v1.2.5-414-release.zip -C C:\Temp\shamiko
2) 推到模块目录（adb push 目录会多套一层，需要拍平）：
   adb shell "mkdir -p /data/adb/modules/zygisk_shamiko"
   adb push C:\Temp\shamiko /data/adb/modules/zygisk_shamiko
   adb shell "cd /data/adb/modules/zygisk_shamiko/shamiko && mv -f * .. && cd .. && rmdir shamiko"
3) 权限（不需要 customize.sh，但 post-fs-data.sh / service.sh / machikado.* / zygisk/*.so 要可执行）：
   adb shell "chmod 755 /data/adb/modules/zygisk_shamiko/*.sh /data/adb/modules/zygisk_shamiko/machikado.* /data/adb/modules/zygisk_shamiko/zygisk/*.so; chmod 644 /data/adb/modules/zygisk_shamiko/module.prop"
4) 确认目录下没有 disable 文件，然后重启：adb shell reboot
5) 重启后重新 adb connect + adb root 再验收。
注意 Shamiko 的 post-fs-data.sh 里 `su -V` 在 MuMu 上会拿不到值（guest 本来就没有 su），但这只会让内置的版本比较失效、不会自我 disable；实测模块保持 enabled=true 且隐藏生效。

## Verification

adb shell "/system/xbin/dusk module list"    # id=zygisk_shamiko, enabled=true
adb shell "ls /data/adb/zygisksu/"            # 出现 no_mount_znctl（Shamiko 的 post-fs-data.sh 跑过的证据）
adb shell "ls /data/adb/post-fs-data.d/"      # 出现 .shamiko_cleanup.sh
并确认它不影响别的模块：ZygiskNext/Vector 仍 enabled=true，zn-daemon / vectord / zn-nsdaemon-* 进程在跑；对 arm64-only 应用验证转译仍正常（logcat: Found /system/lib64/libhoudini.so version 7 / Houdini now in android app mode），LSPosed 模块照旧注入（logcat: Loading Vector/Xposed for <pkg>）。
