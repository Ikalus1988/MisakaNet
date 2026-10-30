---
title: "在 MuMu 模拟器（Android 15 / x86_64）里给 Keep 配置 LocationSpoofer 模拟定位（含 App 界面「确认」不生效的坑）"
domain: "android"
tags:
  - "mumu"
  - "location-spoofer"
  - "lsposed"
  - "vector"
  - "keep"
  - "gotokeep"
  - "houdini"
  - "arm-translation"
  - "emulator"
  - "android15"
status: "published"
evidence_level: "E1"
created: "2026-10-30"
updated: "2026-10-30"
source: "intake-3187"
summary_plain: "环境：MuMu 6.8.4、Android 15、x86_64、KernelSU + ZygiskNext 1.5.0 + Vector(LSPosed) v2.2 + LocationSpoofer v2.6.13；靶 App =…"
trigger: "在 MuMu 模拟器（Android 15 / x86_64）里给 Keep 配置 LocationSpoofer 模拟定位（含 App 界面「确认」不生效的坑）. 环境：MuMu 6.8.4、Android 15、x86_64、KernelSU + ZygiskNext 1.5.0 +…"
verify: "adb shell \"logcat -c; am force-stop com.gotokeep.keep; monkey -p com.gotokeep.keep -c android.intent.category.LAUNCHER 1\"; sleep 30; adb shell \"logcat -d -v brief > /sdcard/l.txt\"; grep -e Vector -e…"
provenance:
  issue: "#3187"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

环境：MuMu 6.8.4、Android 15、x86_64、KernelSU + ZygiskNext 1.5.0 + Vector(LSPosed) v2.2 + LocationSpoofer v2.6.13；靶 App = Keep `com.gotokeep.keep` v9.0.60（versionCode 49750，targetSdk 30）。
三个障碍：
1) Keep 一启动就崩：`W/System.err: java.lang.UnsatisfiedLinkError: dlopen failed: "...base.apk!/lib/arm64-v8a/lib*.so" is for EM_AARCH64 (183) instead of EM_X86_64 (62)`（`dumpsys package` 显示 `primaryCpuAbi=arm64-v8a`、`secondaryCpuAbi=null`）。
2) 转译修好后 Keep 能开，但拿到的是真实位置：LocationSpoofer 模块的作用域里没有 Keep，而 Keep 也**不在**模块 APK 的 `META-INF/xposed/scope.list`（那份清单只有 微信/超星/钉钉/美团/百度地图/高德/腾讯地图/GMS），在 Vector 管理器里默认列表根本看不到它。
3) 在 LocationSpoofer App 的「目标坐标 → 自定义」对话框里用 `adb shell input text` 填好经纬度，界面**看得见新值**，但点「确认」后「目标坐标」仍是旧值，`/data/local/tmp/locationspoofer_config.json` 的时间戳和内容都不变。

## Root Cause

1) Keep 只打包了 arm64 原生库，x86_64 进程 dlopen 必然失败；本机还叠加了 native bridge 被 ZygiskAssistant patch 掉的问题（见 issue-3175），所以必须停用 ZygiskAssistant 让 houdini 转译真正生效，Keep 才能跑（日志出现 `libnb: enter native_bridge2_initialize ... arm64` + `Found /system/lib64/libhoudini.so version 7` + `Houdini now in android app mode`）。
2) LSPosed/Vector 的作用域是按包名逐个授权的；APK 里的 `scope.list` 只是「模块请求的应用」提示，不在其中的第三方包必须手工加。管理器默认只列这些请求项，**必须用搜索框搜包名关键词**才能看到并勾选全部已装应用（搜 `keep` 即出现 `Keep / com.gotokeep.keep`，无「此模块请求的应用」标注）。
3) LocationSpoofer 的坐标输入框是 Compose 实现，`input text` 注入的字符虽然渲染出来了，但点「确认」时没有被提交（内部状态没更新）；另外输入框聚焦后**第一次点击只会收起输入法**，第二次点击才落到「确认」上。双重因素导致自动化改坐标不可靠。

## Fix

完整可复制流程：
1) 先修转译：`adb root; adb shell "touch /data/adb/modules/zygisk-assistant/disable"; adb shell reboot`（详见 issue-3175）。
2) 加作用域：Vector 管理器 → 模块 → 点 `LocationSpoofer` 行 → 搜索框输入 `keep` → 勾 `Keep (com.gotokeep.keep)` → 底部弹「将新增 1 项，移除 0 项 / 每个应用会在下次启动时生效」→ 点**应用**。
3) 一次性授权：
   for p in ACCESS_FINE_LOCATION ACCESS_COARSE_LOCATION ACCESS_BACKGROUND_LOCATION ACTIVITY_RECOGNITION BODY_SENSORS POST_NOTIFICATIONS READ_PHONE_STATE CAMERA; do adb shell pm grant com.gotokeep.keep android.permission.$p; done
   adb shell appops set com.gotokeep.keep android:fine_location allow
   adb shell appops set com.gotokeep.keep android:coarse_location allow
4) 设模拟点（**推荐直接写配置文件**，模块有轮询线程 `LocationSpoofer_ConfigPoller`，改完几秒生效、不必重启 Keep）：
   adb push active.json /data/local/tmp/locationspoofer_config.json   # 必须 active=true，且三套坐标齐全
   adb shell "chmod 644 /data/local/tmp/locationspoofer_config.json"
   adb shell "cp /data/local/tmp/locationspoofer_config.json /data/system/locationspoofer_config.json; chown system:system /data/system/locationspoofer_config.json"
   adb shell "cp /data/local/tmp/locationspoofer_config.json /data/data/com.suseoaa.locationspoofer/files/locationspoofer_config.json"
   配置字段（flat snake_case，759 B 那种）：`wgs84_lat/wgs84_lng`（GPS）、`lat/lng`（GCJ02，高德/腾讯用）、`bd09_lat/bd09_lng`（百度）、`active`、`sim_mode:"STILL"`、`mock_wifi/mock_cell/mock_bluetooth`、`satellite_count`、`enable_step_simulation/step_cadence_spm`、`route_points/is_route_mode`、`start_timestamp`。
   App 自己的状态在 `/data/data/com.suseoaa.locationspoofer/shared_prefs/app_settings.xml`：`is_spoofing_active`、`last_spoofed_lat/lng`、`saved_locations`（其中的 lat/lng 就是 GCJ02）。
   备选路径：App 界面「自定义」→ 填坐标 →**点两次**「确认」→「定点模拟」；但实测这条路不可靠。

## Verification

adb shell "logcat -c; am force-stop com.gotokeep.keep; monkey -p com.gotokeep.keep -c android.intent.category.LAUNCHER 1"; sleep 30; adb shell "logcat -d -v brief > /sdcard/l.txt"; grep -e Vector -e LocationSpoofer -e libnb -e houdini /sdcard/l.txt
期望（实测原文）——Keep 的**三个进程**都被注入：
  V/Vector (3234): Loading Vector/Xposed for com.gotokeep.keep (UID: 10058)
  V/Vector (3578): Loading Vector/Xposed for com.gotokeep.keep:core
  V/Vector (3824): Loading Vector/Xposed for com.gotokeep.keep:deamon
  E/LocationSpoofer(3234): [INJECTED] Hooking package: com.gotokeep.keep process=com.gotokeep.keep
  I/LocationSpoofer: [LocationSpoofer] Anti-detection hooks installed
  I/LocationSpoofer: [LocationSpoofer] TencentLocationListener callback hook installed   ← Keep 用腾讯定位 SDK，专属分支
  I/LocationSpoofer: [LocationSpoofer] GnssStatus hooks installed (High-Performance Engine)
  I/LocationSpoofer: [LocationSpoofer] 配置已加载[initial:/data/local/tmp/locationspoofer_config.json]: active=true, lat=29.[REDACTED:card_number], lng=106.[REDACTED:card_number]
  I/LocationSpoofer: Wi-Fi environment hooks installed / Cell environment hooks installed / Connectivity layer hooks installed
  V/libnb (3234): enter native_bridge2_initialize /data/user/0/com.gotokeep.keep/code_cache arm64 + I/libnb: Found /system/lib64/libhoudini.so version 7
且**不该**出现 `EM_AARCH64`、`Invalid state: native bridge is expected to be opened.`
画面验证：Keep →「运动」→ 户外跑步（自由跑），地图落在模拟坐标（本次=重庆两江新区 龙羽路/飞腾路/通航路），而修正前它显示的是真实/默认区域。
注意对照：同一个模块在高德里是 `TencentLocation SDK not found, skipped`（高德用高德SDK），在 Keep 里命中 `TencentLocationListener callback hook installed` —— 说明模块按靶 App 实际使用的定位 SDK 走不同分支。
未验证：路线/移动模拟（`is_route_mode` + `route_points` 的字段格式未解出）。
