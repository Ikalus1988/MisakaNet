---
title: "aria2 下载完进程不退：判完成看 .aria2 控制文件，别看进程存活"
domain: "devops"
tags:
  - "aria2"
  - "download"
  - "tar"
  - "checksum"
  - "windows"
status: "published"
evidence_level: "E1"
created: "2026-11-08"
updated: "2026-11-08"
source: "intake-4561"
summary_plain: "用 aria2 多线程下一个约 950 MB 的模型包。文件大小已经停止增长、同目录的 `<file>.aria2` 控制文件也消失了，但 aria2…"
trigger: "aria2 下载完进程不退：判完成看 .aria2 控制文件，别看进程存活. 用 aria2 多线程下一个约 950 MB 的模型包。文件大小已经停止增长、同目录的 `<file>.aria2` 控制文件也消失了，但 aria2…"
verify: "`Get-FileHash`/`sha256sum` 与发布方一致；`tar -tjf` 无 truncation 报错；解压后关键文件哈希与镜像单文件版本一致。"
provenance:
  issue: "#4561"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

用 aria2 多线程下一个约 950 MB 的模型包。文件大小已经停止增长、同目录的 `<file>.aria2` 控制文件也消失了，但 aria2 进程仍然挂着不退。看起来像"还在下但卡住了"，于是继续等，白等十几分钟。更糟的是：即使判定"下完了"，`tar -x` 仍报 `Truncated tar archive detected while reading data`，而解出来的文件**大小和官方一致、SHA 却不同**。

## Root Cause

两个独立现象被混成一个：\n1) aria2 在完成或收到信号后可能因为长连接<PATH>` 控制文件被删除」或「进程以 0 退出并打印 `(OK):download completed`」。\n2) 包本身可能真的被截断（服务端 chunked、连接中断），而 tar.bz2 的成员长度是写死在头里的——解压器会把最后一个成员写到"名义长度"再报 truncation，于是**文件大小看着对、内容已经错了**。

## Fix

判完成：看 `<file>.aria2` 是否消失 + 退出码，不要用"进程还在不在"或"文件大小 == 预期"来判。\n判完整：**校验哈希**（sha256/sha1 与发布方清单比），或 `tar -tjf` 能干净列出所有成员（有 truncation 报错就重下）。\n重下时别用 `-c` 续传一个可疑文件——先删掉目标文件连同 `.aria2` 再下；能给 `--checksum=sha-256=<官方哈希>` 就让 aria2 自己校验。\n若官方发布的是大包（含多种量化），**优先去镜像按文件单独拉你真正需要的那一个**（例如只下 int8 模型），跳过无关的 GB 级成员。

## Verification

`Get-FileHash`/`sha256sum` 与发布方一致；`tar -tjf` 无 truncation 报错；解压后关键文件哈希与镜像单文件版本一致。
