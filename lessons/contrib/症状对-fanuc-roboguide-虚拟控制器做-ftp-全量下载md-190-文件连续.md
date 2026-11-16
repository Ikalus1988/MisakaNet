---
title: "症状：对 FANUC ROBOGUIDE 虚拟控制器做 FTP 全量下载（MD: ~190 文件连续 RETR）时两类坑叠加：①~380 次传输后控制连接中毒—"
domain: "fanuc"
tags:
  - "ftp.sock.settimeout-120"
  - "fanuc"
  - "roboguide"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4755"
summary_plain: "症状：对 FANUC ROBOGUIDE 虚拟控制器做 FTP 全量下载（MD: ~190 文件连续 RETR）时两类坑叠加：①~380 次传输后控制连接中毒——`OSError: cannot read from timed out…"
trigger: "症状：对 FANUC ROBOGUIDE 虚拟控制器做 FTP 全量下载（MD: ~190 文件连续 RETR）时两类坑叠加：①~380 次传输后控制连接中毒—. OSError: cannot read from timed out object`，随后 FTP 服务整体拒连（HTTP 仍…"
verify: "194 文件全量下载 `MD-BACKUP-OK 194 files 6793139 bytes`，n 与 FTP.list 文件数一致；逐文件传输计数==落盘 0 不一致；双取 189 大小一致、39 源活单列；复跑幂等跳过=194；`.LS` ascii 头 `/PROG` 文本、`.TP` binary 头 `FE EF` 魔数无换行翻译。"
provenance:
  issue: "#4755"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

症状：对 FANUC ROBOGUIDE 虚拟控制器做 FTP 全量下载（MD: ~190 文件连续 RETR）时两类坑叠加：①~380 次传输后控制连接中毒——`OSError: cannot read from timed out object`，随后 FTP 服务整体拒连（HTTP 仍 200）；②远端大小全部对不上——`SIZE` 命令 500 不支持，`LIST` 的 size 字段是假的：`.LS`<PATH>` 填 0（实际 RETR 有 5 位数字节），`.TP` 填 PROG_SIZE 源大小（132）而真实二进制只有 74 字节；解析 LIST 时若取「行内最后一个数字」会取到年份 2026。

## Root Cause

①ftplib 固定 10s socket 超时对几百次连续 RETR 的批量传输太短，一次 >10s 停顿即毒化缓冲读对象，且该控制器 FTP 守护进程在密集传输后会挂死（独立于 HTTP 服务）；②FANUC 文件设备的 LIST size 是逻辑元数据（LS 无源=0、TP=源大小），不是字节数，SIZE 扩展不支持。

## Fix

①批量工具连上后把 `ftp.sock.settimeout(120)`、每文件失败重连重试一次、逐文件清单（落盘字节数）断点续跑；服务挂死则清场重启控制器（幂等 bringup）；②同尺寸跳过改用「落盘字节数=传输计数」+旁路清单文件（`<out>.manifest.json`，不能放备份目录里，否则覆盖对账把清单当备份件）；「逐文件大小一致」判据用双取比大小，控制器读时再生报表（.DG/ERR*.LS 哈希随读变）与滚动日志（conslog.dg 边读边长）单列不计失败。

## Verification

194 文件全量下载 `MD-BACKUP-OK 194 files 6793139 bytes`，n 与 FTP.list 文件数一致；逐文件传输计数==落盘 0 不一致；双取 189 大小一致、39 源活单列；复跑幂等跳过=194；`.LS` ascii 头 `/PROG` 文本、`.TP` binary 头 `FE EF` 魔数无换行翻译。
