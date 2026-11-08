---
title: "aria2 多线程下载：文件长度已满不等于下载完成，按大小判完成会拿到坏文件"
domain: "devops"
tags:
  - "aria2"
  - "download"
  - "checksum"
  - "cli"
  - "windows"
status: "published"
evidence_level: "E1"
created: "2026-11-08"
updated: "2026-11-08"
source: "intake-4451"
summary_plain: "用 aria2（-x 16 -s 16 --file-allocation=none）下载一个约 184MB 的 APK。磁盘上的文件长度很快变成完整大小，于是按\"文件大小对了\"判定下载完成并结束进程；随后 sha256 与官方…"
trigger: "aria2 多线程下载：文件长度已满不等于下载完成，按大小判完成会拿到坏文件. 用 aria2（-x 16 -s 16 --file-allocation=none）下载一个约 184MB 的…"
verify: "Get-FileHash -Algorithm SHA256 与官方清单逐字符一致；aria2 退出码 0 且日志含 download completed；本地字节数与 release 元数据中的 size 完全相等。"
provenance:
  issue: "#4451"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

用 aria2（-x 16 -s 16 --file-allocation=none）下载一个约 184MB 的 APK。磁盘上的文件长度很快变成完整大小，于是按"文件大小对了"判定下载完成并结束进程；随后 sha256 与官方 SHA256SUMS 完全不符，而字节数一模一样。

## Root Cause

aria2 在开始时就按总长度创建文件（稀疏），之后多条连接各自往自己的偏移区间写数据。文件长度达标只意味着"文件被建到了全长"，不代表每个分片都已落地；这时终止进程，留下的就是"全长但中间有空洞或残留旧数据"的文件，但 ls / Get-ChildItem 看起来完全正常。

## Fix

1) 不要按大小判完成，也不要中途 kill：让它自己退出，看 aria2 输出 (OK):download completed 与退出码。2) 更稳的做法是直接给校验值：--checksum=sha-256=<官方哈希>，aria2 会在完成后自行校验，不一致会报错。3) 已经拿到坏文件时，删掉目标文件连同 .aria2 控制文件重新下载，不要用 -c 续传一个内容不对的文件。

## Verification

Get-FileHash -Algorithm SHA256 与官方清单逐字符一致；aria2 退出码 0 且日志含 download completed；本地字节数与 release 元数据中的 size 完全相等。
