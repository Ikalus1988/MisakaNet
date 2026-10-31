---
title: "自签包的 CFBundleDisplayName 必须是 ASCII：中文名签不了名（同一个坑第二次又犯）"
domain: "mobile"
tags:
  - "sidestore"
  - "infoplist"
  - "cf"
  - "bundledisplayname"
  - "ascii"
  - "localization"
  - "ipa"
  - "packaging"
status: "published"
evidence_level: "E1"
created: "2026-10-31"
updated: "2026-10-31"
source: "intake-4175"
summary_plain: "SideStore 导入 ipa 时报 `An invalid value '百度探针' was provided for the parameter 'appIdName'`，签不过去，App 装不上。"
trigger: "自签包的 CFBundleDisplayName 必须是 ASCII：中文名签不了名（同一个坑第二次又犯）. SideStore 导入 ipa 时报 `An invalid value '百度探针' was provided for the parameter…"
verify: "打包脚本结尾校验显示名是纯 ASCII，不是就 `exit 1`（探针的 pack-ipa.sh 已加）；装好后桌面仍显示中文名。"
provenance:
  issue: "#4175"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

SideStore 导入 ipa 时报 `An invalid value '百度探针' was provided for the parameter 'appIdName'`，签不过去，App 装不上。

## Root Cause

SideStore 自签时把 `CFBundleDisplayName` 直接当 `appIdName` 提交给 Apple，而 Apple 的 `appIdName` 只接受 ASCII。中文写进主 `Info.plist` 就一定炸。

2026-10-25 又犯一次：正式 App 的 `pack-ipa.sh` 早就处理了这件事，但新做的「百度探针」是另写的打包命令，忘了照抄，白装一次。

## Fix

两步都要，缺一不可：

| 位置 | 内容 | 作用 |
|---|---|---|
| 主 `Info.plist` → `CFBundleDisplayName` | `BaiduProbe`（ASCII） | 只给签名用 |
| `zh-Hans.lproj/InfoPlist.strings` | `"CFBundleDisplayName" = "百度探针";` | iOS 桌面读这个 |

```bash
plutil -replace CFBundleDisplayName -string "BaiduProbe" "$APP/Info.plist"
mkdir -p "$APP/zh-Hans.lproj"
printf '"CFBundleDisplayName" = "百度探针";\n' > "$APP/zh-Hans.lproj/InfoPlist.strings"
```

同理 `CFBundleName` / `CFBundleExecutable` / `CFBundleIdentifier` 也必须是 ASCII；但 `NSLocationWhenInUseUsageDescription` 这类描述文案写中文没关系——只有「标识符性质」的字段受限。

教训：**「已经有脚本做过的事」，新脚本必须照抄，不能凭记忆手敲**。判据很简单——手敲的打包命令里没有 `plutil -replace CFBundleDisplayName` 这一行，就一定会踩。

## Verification

打包脚本结尾校验显示名是纯 ASCII，不是就 `exit 1`（探针的 pack-ipa.sh 已加）；装好后桌面仍显示中文名。
