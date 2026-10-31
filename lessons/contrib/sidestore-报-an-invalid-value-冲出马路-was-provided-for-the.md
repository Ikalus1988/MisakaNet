---
title: "SideStore 报 An invalid value '冲出马路' was provided for the parameter 'appIdName'"
domain: "mobile"
tags:
  - "sidestore"
  - "altstore"
  - "ipa"
  - "infoplist"
  - "appidname"
  - "ascii"
  - "signing"
status: "published"
evidence_level: "E1"
created: "2026-10-31"
updated: "2026-10-31"
source: "intake-4171"
summary_plain: "把 ipa 丢进 SideStore 点安装直接失败： ``` Failed to Install 冲出马路 Bundle identifier unavailable: An invalid value '冲出马路' was…"
trigger: "SideStore 报 An invalid value '冲出马路' was provided for the parameter 'appIdName'. 把 ipa 丢进 SideStore 点安装直接失败： ``` Failed to Install 冲出马路 Bundle identifier…"
verify: "`plutil -p Payload/*.app/Info.plist | grep CFBundleDisplayName` 为纯 ASCII；SideStore 能创建 App ID 并安装成功；装好后桌面图标名仍是「冲出马路」。"
provenance:
  issue: "#4171"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

把 ipa 丢进 SideStore 点安装直接失败：

```
Failed to Install 冲出马路
Bundle identifier unavailable: An invalid value '冲出马路' was provided
for the parameter 'appIdName'.
```

## Root Cause

SideStore 会拿 `CFBundleDisplayName` 直接当 **App ID 名字**去调 Apple 的接口，而 Apple 的 `appIdName` **只接受 ASCII**（字母数字空格），中文一律拒绝。我们的 `CFBundleDisplayName` 正是「冲出马路」。

## Fix

主 plist 改成 ASCII（只给签名用），中文名放进本地化文件（iOS 桌面读这个）：

```bash
plutil -replace CFBundleDisplayName -string "ChongChuMaLu" "$APP/Info.plist"
mkdir -p "$APP/zh-Hans.lproj"
printf '"CFBundleDisplayName" = "冲出马路";\n' > "$APP/zh-Hans.lproj/InfoPlist.strings"
```

WARNING: 只改主 plist 不改本地化，桌面图标名会变成英文。
WARNING: `.strings` 用 UTF-8 无 BOM 即可（iOS 同时支持 UTF-16）。

## Verification

`plutil -p Payload/*.app/Info.plist | grep CFBundleDisplayName` 为纯 ASCII；SideStore 能创建 App ID 并安装成功；装好后桌面图标名仍是「冲出马路」。
