---
title: "开发签名 ipa ≠ 自签 ipa：去签名要做四件事，缺一个 SideStore 就报错"
domain: "mobile"
tags:
  - "ipa"
  - "codesign"
  - "sidestore"
  - "mobileprovision"
  - "unsigned"
  - "quarantine"
  - "packaging"
status: "published"
evidence_level: "E1"
created: "2026-10-31"
updated: "2026-10-31"
source: "intake-4172"
summary_plain: "开发签名打出来的 ipa 拿到别人手机上装不上；直接丢给 SideStore 也报错，搞不清该用哪种包。"
trigger: "开发签名 ipa ≠ 自签 ipa：去签名要做四件事，缺一个 SideStore 就报错. 开发签名打出来的 ipa 拿到别人手机上装不上；直接丢给 SideStore 也报错，搞不清该用哪种包。"
verify: "`codesign -dv Payload/*.app` 报 `code object is not signed at all`；`otool -l` 里 `LC_ENCRYPTION_INFO` 的 cryptid 是 0；SideStore 能正常重签安装。"
provenance:
  issue: "#4172"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

开发签名打出来的 ipa 拿到别人手机上装不上；直接丢给 SideStore 也报错，搞不清该用哪种包。

## Root Cause

两者定位完全不同：

| | 开发签名（默认） | 去签名（--unsigned） |
|---|---|---|
| 能装到哪 | 只有描述文件里注册过的设备 | 任何设备（SideStore 用你的 Apple ID 重签） |
| 有效期 | 跟描述文件 | 免费账号 7 天，要回 SideStore 刷新 |
| 包里带什么 | `_CodeSignature` + `embedded.mobileprovision` | 全部剥掉，二进制无签名 |
| 谁签的 | 我的 Team | 用户自己的 Apple ID |

去签名只做一半会留下串证书的残留，SideStore 一样装不上。

## Fix

四件事缺一不可：

```bash
codesign --remove-signature "$APP/BMSiOS"   # 1 主二进制
rm -rf "$APP/_CodeSignature"                # 2 签名目录
rm -f  "$APP/embedded.mobileprovision"      # 3 描述文件（绑的是我的 Team，会串证书）
xattr -cr "$APP"                            # 4 清 quarantine，macOS 会挡住重签
```

另外必须确认 `LC_ENCRYPTION_INFO cryptid == 0`：App Store 的包是加密的，自签工具签不了。

## Verification

`codesign -dv Payload/*.app` 报 `code object is not signed at all`；`otool -l` 里 `LC_ENCRYPTION_INFO` 的 cryptid 是 0；SideStore 能正常重签安装。
