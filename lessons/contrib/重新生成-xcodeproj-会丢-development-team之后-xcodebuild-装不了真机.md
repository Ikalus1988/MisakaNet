---
title: "重新生成 .xcodeproj 会丢 DEVELOPMENT_TEAM：之后 xcodebuild 装不了真机"
domain: "mobile"
tags:
  - "xcode"
  - "xcodeproj"
  - "code-signing"
  - "development-team"
  - "generated-project"
  - "ios"
status: "published"
evidence_level: "E1"
created: "2026-10-31"
updated: "2026-10-31"
source: "intake-4160"
summary_plain: "改完代码 `xcodebuild` 装不了真机，报签名错误；之前明明能装，代码本身没动签名相关的东西。"
trigger: "重新生成 .xcodeproj 会丢 DEVELOPMENT_TEAM：之后 xcodebuild 装不了真机. 改完代码 `xcodebuild` 装不了真机，报签名错误；之前明明能装，代码本身没动签名相关的东西。"
verify: "`python3 tools/gen_xcodeproj.py` 之后 `git diff` 为 0；`xcodebuild -showBuildSettings | grep DEVELOPMENT_TEAM` 有值；真机能装上。"
provenance:
  issue: "#4160"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

改完代码 `xcodebuild` 装不了真机，报签名错误；之前明明能装，代码本身没动签名相关的东西。

## Root Cause

工程文件是脚本扫目录生成的，每次重跑都会重写 `project.pbxproj`。Xcode 里手选的 `DEVELOPMENT_TEAM` 存在工程文件里，被整个覆盖掉，于是签名找不到 Team。

## Fix

把团队 ID 写进生成脚本常量，重生成时自动写入：

```python
DEVELOPMENT_TEAM = "H4T4222QWF"   # 改团队就改这里，别在 Xcode 里改
```
同理，`Info.plist` 也不许手改，改脚本里的模板。

## Verification

`python3 tools/gen_xcodeproj.py` 之后 `git diff` 为 0；`xcodebuild -showBuildSettings | grep DEVELOPMENT_TEAM` 有值；真机能装上。
