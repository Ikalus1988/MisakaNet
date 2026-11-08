---
title: "aria2 --stop 沿用到真实下载，大文件被静默截断且伪装成已完成"
domain: "devops"
tags:
  - "aria2"
  - "download"
  - "zip"
  - "corrupt"
  - "truncated"
status: "published"
evidence_level: "E1"
created: "2026-11-08"
updated: "2026-11-08"
source: "intake-4439"
summary_plain: "从 GitHub codeload 下载 ComfyUI 源码 zip（约 13MB），aria2 报 (OK) 完成、目录里也没有 .aria2 控制文件残留，看起来一切正常。但解压时报： - bsdtar: ZIP…"
trigger: "aria2 --stop 沿用到真实下载，大文件被静默截断且伪装成已完成. 从 GitHub codeload 下载 ComfyUI 源码 zip（约 13MB），aria2 报 (OK) 完成、目录里也没有 .aria2…"
verify: "1. tar -tf <zip> 无报错且条目数合理 2. 解压后关键文件存在（如 main.py / package.json） 3. safetensors 理论大小与实际大小一致"
provenance:
  issue: "#4439"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

从 GitHub codeload 下载 ComfyUI 源码 zip（约 13MB），aria2 报 (OK) 完成、目录里也没有 .aria2 控制文件残留，看起来一切正常。但解压时报：
- bsdtar: ZIP decompression failed (-5)
- .NET: End of Central Directory record could not be found

根因是把测速脚本里的 --stop=60 直接沿用到了真实下载命令上。

## Root Cause

1. aria2 的 --stop=SEC 语义是"进程运行 N 秒后退出"，与下载是否完成无关；在真实下载里等于强制中断。
2. aria2 下载完成后会删除 .aria2 控制文件，所以"没有控制文件"常被误读为"已完成"，实际中断时该文件也可能已被清理或从未可见。
3. codeload.github.com 返回 chunked 编码、无 Content-Length，无法用文件大小判断完整性。

三者叠加，造成"看起来下完了，实际内容截断"的静默失败。

## Fix

1. 测速与真实下载分成两条独立命令。测速可以带 --stop，但必须输出到临时目录并在测完立即删除。
2. 真实下载命令里不要出现 --stop。
3. 下载后立刻做结构校验，不要靠"完成"日志判断：
   - zip: tar -tf <file> 能列出条目，或 [System.IO.Compression.ZipFile]::OpenRead(path) 不抛异常
   - safetensors: 读前 8 字节得到 header 长度，解析 JSON 的 data_offsets，最大值 + 8 + header 长度 应等于文件大小

## Verification

1. tar -tf <zip> 无报错且条目数合理
2. 解压后关键文件存在（如 main.py / package.json）
3. safetensors 理论大小与实际大小一致
