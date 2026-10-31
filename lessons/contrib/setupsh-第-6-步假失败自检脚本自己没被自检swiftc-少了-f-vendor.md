---
title: "setup.sh 第 6 步「假失败」：自检脚本自己没被自检（swiftc 少了 -F Vendor）"
domain: "devops"
tags:
  - "bash"
  - "ci"
  - "self-check"
  - "typecheck"
  - "swiftc"
  - "frameworks"
  - "false-negative"
status: "published"
evidence_level: "E1"
created: "2026-10-31"
updated: "2026-10-31"
source: "intake-4178"
summary_plain: "新机器 `git clone` → `bootstrap.sh` → `setup.sh`：第 5 步 OK BUILD SUCCEEDED，第 6 步却报： ``` FAIL 有编译错误，详见 <PATH>…"
trigger: "setup.sh 第 6 步「假失败」：自检脚本自己没被自检（swiftc 少了 -F Vendor）. 新机器 `git clone` → `bootstrap.sh` → `setup.sh`：第 5 步 OK BUILD SUCCEEDED，第 6 步却报： ``` FAIL…"
verify: "新机器跑完 `setup.sh`：第 5、6 步都通过；故意删掉 `-F Vendor` 能复现该报错，证明判据真的覆盖到了。"
provenance:
  issue: "#4178"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

新机器 `git clone` → `bootstrap.sh` → `setup.sh`：第 5 步 OK BUILD SUCCEEDED，第 6 步却报：

```
FAIL 有编译错误，详见 <PATH>
BMSiOS/UI/AMapContainer.swift:24:8: error: no such module 'AMapNaviKit'
```

新人第一反应是「代码坏了」，去改本来没问题的代码。

## Root Cause

第 6 步是另一条独立的 `swiftc -typecheck` 命令，**没带 `-F Vendor`**。`AMapNaviKit.framework` 在 `Vendor/` 里，搜索路径不给当然找不到——真正的工程编译（第 5 步）是通的，所以这是**自检脚本自己的 bug**。

## Fix

给 `swiftc` 补上 framework 搜索路径，并把写死的数字改成动态计数：

```bash
swiftc -typecheck -F "$HERE/Vendor" -sdk "$(xcrun --sdk iphoneos --show-sdk-path)" \
  $(find BMSiOS -name '*.swift')
```

判据：任何「和主构建并行的第二套检查」都要**对齐主构建的参数**（SDK、framework 搜索路径、target、编译开关）。文档里写死的数字（如「11 个 Swift 文件」）一定会过期，能算就别写死。

## Verification

新机器跑完 `setup.sh`：第 5、6 步都通过；故意删掉 `-F Vendor` 能复现该报错，证明判据真的覆盖到了。
