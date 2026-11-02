---
title: "macOS 自带 bash 3.2 两个雷：set -u 下展开空数组、变量后紧跟全角括号"
domain: "devops"
tags:
  - "bash"
  - "macos"
  - "bash3"
  - "set-u"
  - "array"
  - "unbound-variable"
  - "encoding"
status: "published"
evidence_level: "E1"
created: "2026-11-02"
updated: "2026-11-02"
source: "intake-4157"
summary_plain: "脚本在自己机器上好好的，换台 Mac 直接失败：一个报 `unbound variable`，一个报完全看不懂的变量名。"
trigger: "macOS 自带 bash 3.2 两个雷：set -u 下展开空数组、变量后紧跟全角括号. 脚本在自己机器上好好的，换台 Mac 直接失败：一个报 `unbound variable`，一个报完全看不懂的变量名。"
verify: "空数组、空变量、中文后缀三种情况跑一遍都不报 unbound variable；`bash --version` 显示 3.2.x。"
provenance:
  issue: "#4157"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

脚本在自己机器上好好的，换台 Mac 直接失败：一个报 `unbound variable`，一个报完全看不懂的变量名。

## Root Cause

macOS 自带的是 bash 3.2（2007 年）：
1. `set -u` 下展开空数组 `"${ARR[@]}"` 会报 unbound variable，整条命令失败；
2. 变量后紧跟全角括号/中文时，多字节字符的字节会被算进变量名（`"$size）"` 会把 `）` 当标识符）。

## Fix

```bash
# 1) 空数组安全展开
rm -f "${ARR[@]+\"${ARR[@]}\"}"

# 2) 变量后面接中文/全角一律加花括号
echo "大小=${size}）"
echo "非 ASCII：${DISP}，会拒签"
```
要彻底避坑：能用 python 就别用 bash 写逻辑；或 `#!<PATH> bash` + 版本检测。

## Verification

空数组、空变量、中文后缀三种情况跑一遍都不报 unbound variable；`bash --version` 显示 3.2.x。
