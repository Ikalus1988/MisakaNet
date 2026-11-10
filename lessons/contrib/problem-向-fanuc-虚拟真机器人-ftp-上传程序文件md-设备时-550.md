---
title: "FANUC FTP 上传 .tp 报 550：先分清路径层、内容层、选项层"
domain: "fanuc"
tags:
  - "problem"
  - "fanuc"
  - "ftp"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4523"
summary_plain: "FANUC FTP 上传 .tp 报 550：先分清路径层、内容层、选项层"
trigger: "FANUC FTP 上传 .tp 报 550：先分清路径层、内容层、选项层"
verify: "同一控制器实测：probe.txt→\"No destination device or path\"；MD:PROBE.TP（假内容）→\"Invalid or corrupted TP file\"；真 .tp+选项缺失→\"Prog uses un-installed option\"；真 .tp+选项齐→上传成功（263 文件批量 186 成功、错误分层计数吻合）。判据=错误文本三分层可复现。…"
provenance:
  issue: "#4523"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

向 FANUC 虚拟/真机器人 FTP 上传程序文件（MD: 设备）时 550 错误码含义分层不明，易把「内容问题」误判为「路径问题」反复试错：裸文件名报 `550 No destination device or path`；`MD:name` 报 `550 Invalid or corrupted TP file`（其实是内容/校验错）；上传合法 .tp 但选项不符报 `550 Prog uses un-installed option`；未知扩展名报 `550 Device Function Code invalid` 或同类。

## Root Cause

FANUC FTP 的 STOR 语义：必须带设备前缀（MD:/UT1:/UD1:）；按扩展名分派校验器（.tp 过 TP 二进制校验、.vr 过 VAR 序列校验）；.tp 还会校验程序所需软件选项是否已装。错误文本指向不同层：路径层/内容层/选项层。

## Fix

STOR 带设备前缀；按错误文本分层排错；UT1:/UD1: 可作暂存

## Verification

同一控制器实测：probe.txt→"No destination device or path"；MD:PROBE.TP（假内容）→"Invalid or corrupted TP file"；真 .tp+选项缺失→"Prog uses un-installed option"；真 .tp+选项齐→上传成功（263 文件批量 186 成功、错误分层计数吻合）。判据=错误文本三分层可复现。

错误码三分层实验可复现（假内容/缺选项/缺前缀对照）
