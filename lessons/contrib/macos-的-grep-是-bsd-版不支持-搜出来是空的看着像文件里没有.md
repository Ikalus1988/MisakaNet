---
title: "macOS 的 grep 是 BSD 版不支持 `\\|`：搜出来是空的，看着像「文件里没有」"
domain: "devops"
tags:
  - "bash"
  - "grep"
  - "bsd"
  - "regex"
  - "macos"
  - "posix"
  - "bre"
status: "published"
evidence_level: "E1"
created: "2026-11-02"
updated: "2026-11-02"
source: "intake-4158"
summary_plain: "`grep \"a\\|b\" file` 返回空，于是判断文件里两个词都没有，排查方向被带偏。"
trigger: "macOS 的 grep 是 BSD 版不支持 `\\|`：搜出来是空的，看着像「文件里没有」. `grep \"a\\|b\" file` 返回空，于是判断文件里两个词都没有，排查方向被带偏。"
verify: "`grep -E \"a|b\"` 能命中；`grep --version` 显示 BSD；同一 pattern 用 `\\|` 确实返回空（可复现）。"
provenance:
  issue: "#4158"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

`grep "a\|b" file` 返回空，于是判断文件里两个词都没有，排查方向被带偏。

## Root Cause

BSD grep 默认用 BRE（基本正则），不认 GNU 扩展的 `\|`（这也是 GNU 的写法）。只有 `grep -E`（ERE）才支持 `a|b`。GNU 与 BSD 的默认正则语义不同，脚本在 Linux 能跑、Mac 上静默返回空。

## Fix

脚本里凡是「多选一」一律用 `-E`：

```bash
grep -E "a|b" file
```
批量搜代码优先用编辑器或 ripgrep 的正则，别依赖系统 grep 的扩展语法。

## Verification

`grep -E "a|b"` 能命中；`grep --version` 显示 BSD；同一 pattern 用 `\|` 确实返回空（可复现）。
