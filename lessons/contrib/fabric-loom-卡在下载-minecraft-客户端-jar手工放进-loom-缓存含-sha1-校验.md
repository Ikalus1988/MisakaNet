---
title: "Fabric Loom 卡在下载 Minecraft 客户端 jar：手工放进 loom 缓存（含 SHA1 校验）"
domain: "development"
tags:
  - "minecraft"
  - "fabric"
  - "loom"
  - "gradle"
  - "download"
status: "published"
evidence_level: "E1"
created: "2026-11-20"
updated: "2026-11-20"
source: "intake-5114"
summary_plain: "首次构建 Fabric mod 工程，Loom 卡在下载客户端 jar： ~/.gradle/caches/fabric-loom/<mcver><PATH> 恒为 0 字节然后极慢增长 等了 20 分钟只下 1.4MB（约…"
trigger: "Fabric Loom 卡在下载 Minecraft 客户端 jar：手工放进 loom 缓存（含 SHA1 校验）. 首次构建 Fabric mod 工程，Loom 卡在下载客户端 jar： ~/.gradle/caches/fabric-loom/<mcver><PATH> 恒为 0 字节然后极慢增长 等了…"
verify: "1) SHA1 与 version json 完全一致； 2) 重新 build 不再生成 .part，下载阶段被跳过； 3) 缓存目录出现 minecraft-merged.jar / minecraft-extracted_server.jar 等后续产物。"
provenance:
  issue: "#5114"
  source: "MCP intake (dsh), lesson submission converted by the maintainer"
---

## Problem

首次构建 Fabric mod 工程，Loom 卡在下载客户端 jar：

~/.gradle/caches/fabric-loom/<mcver><PATH>  恒为 0 字节然后极慢增长

等了 20 分钟只下 1.4MB（约 1KB/s），同一次构建里 server jar（59MB）却很快下完。build 既不报错也不前进。

## Root Cause

Loom 用 HttpURLConnection 直接从 piston-data.mojang.com 拉客户端 jar，无断点续传、无多线程；该源在国内吞吐可低到 1KB/s，于是表现为"永久卡住"而不是"失败"。

## Fix

1) 从缓存里的 mojang_minecraft_info.json（或 version json）读 downloads.client.url 与 downloads.client.sha1
2) 多线程下载器拉完整 jar（aria2 -x16 -s16 -k1M）
3) Get-FileHash 校验 SHA1 必须与 json 一致
4) 放到 ~/.gradle/caches/fabric-loom/<mcver><PATH>
5) 删掉同目录的 minecraft-client.jar.part（不删会接着从断点爬）
6) 重新 build

## Verification

1) SHA1 与 version json 完全一致；
2) 重新 build 不再生成 .part，下载阶段被跳过；
3) 缓存目录出现 minecraft-merged.jar / minecraft-extracted_server.jar 等后续产物。
