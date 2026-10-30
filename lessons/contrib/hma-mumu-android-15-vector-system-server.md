---
title: "HMA（隐藏应用列表）在 MuMu Android 15 上「模块已激活 / 系统服务未运行」且界面冻结：Vector 从未把它注入 system_server"
domain: "android"
tags:
  - "mumu"
  - "hidemyapplist"
  - "hma"
  - "lsposed"
  - "vector"
  - "system-server"
  - "app-list-hiding"
  - "emulator"
  - "android15"
  - "ui-freeze"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-3188"
summary_plain: "环境：MuMu 6.8.4（Android 15 / x86_64）、KernelSU（ksud 3.2.5）+ ZygiskNext 1.5.0 + Vector(LSPosed) v2.2，隐藏应用列表 HMA…"
trigger: "HMA（隐藏应用列表）在 MuMu Android 15 上「模块已激活 / 系统服务未运行」且界面冻结：Vector 从未把它注入 system_server. 环境：MuMu 6.8.4（Android 15 / x86_64）、KernelSU（ksud 3.2.5）+ ZygiskNext 1.5.0 +…"
verify: "① `adb shell \"cat /data/adb/lspd/log/verbose_*.log\" | grep -e \"Injected Vector framework into system_server\" -e \"com.tsng.hidemyapplist\"` → 只有前者命中、**没有任何 `Loading module com.tsng.hidemyapplist`**； ②…"
provenance:
  issue: "#3188"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

环境：MuMu 6.8.4（Android 15 / x86_64）、KernelSU（ksud 3.2.5）+ ZygiskNext 1.5.0 + Vector(LSPosed) v2.2，隐藏应用列表 HMA `com.tsng.hidemyapplist` V3.8.3.r520.9605640（API 101）。
在 Vector 管理器里启用 HMA 模块、作用域勾选 System Framework (system_server)（该条目自带「由模块固定」标注）并点了「应用」，重启后打开 HMA：
1) 首页顶部横幅显示「模块已激活 [3.8.3-520] / **系统服务未运行**」；
2) 界面**完全冻结**：弹出的「更新 V3.3.1」对话框点「确定」关不掉，`input keyevent 4` 也无效，连续 `screencap` 拿到的 PNG **字节完全相同**（SHA256 `61A5E49B…`，只有状态栏时钟在走），`am force-stop` 之后界面才恢复；冻结期间 `dumpsys window` 的 `mCurrentFocus` 始终是 `com.tsng.hidemyapplist/.MainActivityLauncher`；
3) HMA 配置根本没生成：`/data/data/com.tsng.hidemyapplist/files/config.json` 只有 **128 B**，`shared_prefs/` 为空，`/data/system` 下没有任何 hidemyapplist 目录。

## Root Cause

HMA 的「隐藏应用列表」能力依赖它自己的 Xposed 模块被注入 **system_server**（这正是那条 scope 项「由模块固定」的含义）。本机 Vector 框架本身是好的：`/data/adb/lspd/log/verbose_2026-10-13T12:02:50.451692.log` 里有 `I/VectorNative: Injected Vector framework into system_server.`、`I/VectorConfigCache: System services are ready. Mapping modules and scopes.`、`I/VectorManager: modules: scanned 79 packages in 14ms, opened 3`、以及 `D/VectorModuleAppService: Sent module binder to com.tsng.hidemyapplist`（只是把 binder 发给了 App 进程）。但**整份 verbose 日志里没有任何 `Loading module com.tsng.hidemyapplist`**；同批拉取的 `modules_2026-10-13T12:02:50.45615.log` 里也只有 `com.suseoaa.locationspoofer` 注入 Keep 三个进程的记录。⇒ HMA 从未进入 system_server，它的系统服务自然「未运行」，UI 在等待该服务时把主线程卡死（无 ANR 日志、输入事件全丢——不是 adb 坐标算错，同一坐标在别的应用上正常）。

## Fix

本 ROM 组合下 HMA 3.8.3 不可用，不要在它身上继续花时间：
1) 解冻：`adb shell am force-stop com.tsng.hidemyapplist`（进程退出后界面立刻恢复正常）。
2) 隐藏需求改用 **Shamiko**：它是挂载命名空间级隐藏，实测在本机（KernelSU 3.2.5 + ZygiskNext 1.5.0）不影响 houdini 转译，也不影响 LSPosed 模块注入。
3) 若一定要用 HMA：换更新的 HMA 版本、确认 Vector 里该模块作用域确实含 System Framework 后重启，或更换框架/ROM 组合再试；排查时先看 `/data/adb/lspd/log/verbose_*.log` 里有没有 `Loading module <包名>`。
4) 决策依据：多数定位类靶应用（Keep 9.0.60、高德 17.01）并不枚举已装应用列表，缺 HMA 不影响模拟定位用途；真正需要隐藏 root/框架的场合优先考虑 Shamiko + 按包 Umount modules。

## Verification

① `adb shell "cat /data/adb/lspd/log/verbose_*.log" | grep -e "Injected Vector framework into system_server" -e "com.tsng.hidemyapplist"` → 只有前者命中、**没有任何 `Loading module com.tsng.hidemyapplist`**；
② 打开 HMA 首页看横幅是否仍写「系统服务未运行」；
③ `ls -l /data/data/com.tsng.hidemyapplist/files/config.json` = 128 B（配置从未生成）、`ls /data/system | grep -i hidemy` 无输出；
④ 冻结判定技巧：连拍两张 `screencap` 比较 SHA256，若完全相同且只有状态栏时钟变化即为 UI 冻结（可再补发 `input keyevent 224` + `wm dismiss-keyguard` 排除「屏幕未唤醒」导致的假冻结）；
⑤ 隐藏是否真的生效要另找会枚举应用列表的检测应用来验证，不能只看 HMA 自己的横幅。
