---
title: "MuMu 模拟器里没有 su（KernelSU 的 ksud 被改名 /system/xbin/dusk）——用 busybox 顶替 su 才能让 App 拿到 root"
domain: "android"
tags:
  - "mumu"
  - "kernelsu"
  - "ksud"
  - "dusk"
  - "su"
  - "adb-root"
  - "sucompat"
  - "emulator"
  - "android15"
  - "root"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-3177"
summary_plain: "MuMu 6.8.4（Android 15 / x86_64，自带 KernelSU）里 shell 层完全没有 su： adb shell su -c id → /system/bin/sh: su: inaccessible or…"
trigger: "MuMu 模拟器里没有 su（KernelSU 的 ksud 被改名 /system/xbin/dusk）——用 busybox 顶替 su 才能让 App 拿到 root. MuMu 6.8.4（Android 15 / x86_64，自带 KernelSU）里 shell 层完全没有 su： adb shell…"
verify: "adb shell \"ls -l /system/xbin/su\" # -rwxr-xr-x 1 root root 1325608（busybox 拷贝） 然后打开目标 App（LocationSpoofer）→ 不再停在「需要 Root 权限」页，而是正常进入主界面，并且真的以 root 写文件： adb shell \"ls -l…"
public_analogue: "busybox"
provenance:
  issue: "#3177"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

MuMu 6.8.4（Android 15 / x86_64，自带 KernelSU）里 shell 层完全没有 su：
  adb shell su -c id      → /system/bin/sh: su: inaccessible or not found   (rc=127)
  adb shell ls -l /system/bin/su /system/xbin/su → No such file or directory
  adb shell "ls -l /system/bin | grep -i -e rws -e suid"  → 没有任何 setuid 二进制
可是 KernelSU 管理器（预装包 me.weishu.kernelsu）显示「工作中 <GKI> 版本 32525-2 / 管理器版本 v3.2.5 (32525-2)」，即内核驱动是好的。
连带现象：
1) 用 KernelSU 装模块时 `dusk module install /data/local/tmp/x.zip` 报 `Error: Permission denied (os error 13)`；
2) LSPosed 模块类 App（如 LocationSpoofer v2.6.13）启动即卡在「需要 Root 权限 / 本应用需要 KernelSU Root 权限才能运行」页，永远进不去；
3) `su 0 id`、`/system/bin/su -c id`、`/data/adb/ksu/bin/su` 全部失败。

## Root Cause

两个被误判的点：
1) MuMu 的「Root 权限」开关（设置→开发者选项→Root 权限，或 MuMuManager.exe setting -k root_permission -val true）实现的不是 su 二进制，而是 **root adb**：执行 `adb root` 后 `id` 返回 `uid=0(root) gid=0(root) ... context=u:r:su:s0`（KernelSU 的 su 域）。guest 镜像里压根没有 su，也没有 setuid 的 su。所以「找不到 su」不是故障，是设计。
2) KernelSU 的用户态 CLI（ksud 3.2.5，versionCode 32525）被网易改名为 `/system/xbin/dusk`（3,753,880 B，与 `/data/adb/ksud` 同尺寸；`dusk -V` = `ksud 3.2.5`；`dusk -h` = `KernelSU userspace cli`，子命令有 install / module / uninstall / sepolicy / profile / late-load ...）。它只吃子命令，**不能当 su 用**：`dusk -c id` → `error: unexpected argument '-c' found`。
3) KernelSU 的 sucompat 是**按「文件名 su」拦截 execve** 来提权的（不依赖 setuid 位）。因此在 guest 的 PATH 目录里放一个名为 su 的可执行文件，App 调 `su -c ...` 时就会被内核 hook 接管并提权成功；而 adb shell（uid 2000、shell 域）即使执行同名文件也不会被放行 —— 这也解释了为什么 shell 侧测试永远失败、App 侧却立刻成功。

## Fix

步骤（系统盘必须可写：设置→磁盘设置→磁盘共享→可写系统盘，然后重启）：
  # 1) 先把 MuMu 的「Root 权限」打开，再拿到 root adb
  E:\MuMuPlayer\nx_main\adb.exe connect 127.0.0.1:16384
  E:\MuMuPlayer\nx_main\adb.exe root            # → restarting adbd as root
  E:\MuMuPlayer\nx_main\adb.exe shell id        # uid=0(root) ... context=u:r:su:s0

  # 2) 给 App 造一条 su 通道（把 busybox 拷成 su，不需要 setuid 位）
  adb shell "cp /system/xbin/busybox /system/xbin/su; chmod 755 /system/xbin/su"

  # 3) 装 KernelSU 模块不要用 su，用 dusk（务必先 adb root，否则 Permission denied (os error 13)）
  adb push Zygisk-Next-1.5.0-843-5217106-release.zip /data/local/tmp/
  adb shell "dusk module install /data/local/tmp/Zygisk-Next-1.5.0-843-5217106-release.zip"
  adb shell "dusk module list"      # 结果先落在 /data/adb/modules_update/，重启后才生效

注意：ZygiskNext 的安装器会在 KernelSU 上做 check_sepolicy；实测 MuMu 6.8.4 的内核（6.1.90-perf+）能通过，不会出现 “! Unable to apply SELinux patches!”。

## Verification

adb shell "ls -l /system/xbin/su"     # -rwxr-xr-x 1 root root 1325608（busybox 拷贝）
然后打开目标 App（LocationSpoofer）→ 不再停在「需要 Root 权限」页，而是正常进入主界面，并且真的以 root 写文件：
adb shell "ls -l /data/system/locationspoofer_config.json"   # -rw-r--r-- system system（App 自己 chown 出来的）
反证（说明 root 来自内核 hook、不是 busybox 给的）：
adb unroot ; adb shell "su -c id"   → su: applet not found（shell 域不被 KernelSU 放行）
系统盘可写是否持久：
adb shell "grep ' /system ' /proc/mounts"   → overlay ... upperdir=/mnt/scratch/upperdir（重启后 /system/xbin/su 仍在）
