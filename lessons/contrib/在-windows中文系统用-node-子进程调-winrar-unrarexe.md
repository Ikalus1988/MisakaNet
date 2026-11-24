---
title: "在 Windows（中文系统）用 Node 子进程调 WinRAR UnRAR.exe 列目录（`lb`）拿到文件名，再用该文件名调 `p` 提"
domain: "windows"
tags:
  - "lb"
  - "windows"
  - "node"
status: "published"
evidence_level: "E1"
created: "2026-11-24"
updated: "2026-11-24"
source: "intake-5702"
summary_plain: "在 Windows（中文系统）用 Node 子进程调 WinRAR UnRAR.exe 列目录（`lb`）拿到文件名，再用该文件名调 `p` 提取——提取静默失败（stdout 0 字节），而 lb…"
trigger: "UnRAR lb 输出 GBK 文件名乱码 提取 0 字节 静默失败 Windows OEM 代码页 TextDecoder gbk"
verify: "同一 archive：gbk 解码后的文件名传 `p` 提取成功（实测单文件 21987 字节，status 0）；utf8 解码同名调用 0 字节。批量口径：全量跑 430 个目标文件提取零空件即通过。 gbk 解码文件名重试提取 status 0 且字节数>0；全量提取零空件；utf8 对照组 0 字节。"
provenance:
  issue: "#5702"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

在 Windows（中文系统）用 Node 子进程调 WinRAR UnRAR.exe 列目录（`lb`）拿到文件名，再用该文件名调 `p` 提取——提取静默失败（stdout 0 字节），而 lb 看起来「正常」（终端里只是显示乱码）。同样的模式适用于任何 Windows 中文环境 CLI 工具的控制台输出（rar/压缩工具/legacy exe）。

## Root Cause

UnRAR 的控制台输出走系统 OEM/ANSI 代码页（zh-CN = GBK）。脚本按 utf8 解码 → 中文目录名变乱码字符串；把乱码串作为参数传回 `p` 时与压缩包内的 Unicode 文件名匹配不上 → 无文件命中 + `-inul` 抑制提示 = 静默 0 字节。ls/列表类输出「看起来有内容」，失败只在下一跳暴露——症状是下游参数失配，不是解码报错。

## Fix

捕获 Windows 中文环境 CLI 的 stdout 后用 `TextDecoder('gbk')`（Node 的 Buffer 不支持 'gbk' 编码名，要用 TextDecoder）解码文件名；把解码后的正确名字作为参数传回（Node spawnSync 会按 UTF-16 传参，工具能正确匹配）。判别信号：终端里文件名显示乱码、或下游提取/匹配得到 0 字节而 exit code 正常。

## Verification

同一 archive：gbk 解码后的文件名传 `p` 提取成功（实测单文件 21987 字节，status 0）；utf8 解码同名调用 0 字节。批量口径：全量跑 430 个目标文件提取零空件即通过。

gbk 解码文件名重试提取 status 0 且字节数>0；全量提取零空件；utf8 对照组 0 字节。
