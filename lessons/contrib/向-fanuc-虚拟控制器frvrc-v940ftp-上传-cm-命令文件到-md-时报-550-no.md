---
title: "向 FANUC 虚拟控制器（FRVRC V9.40）FTP 上传 .CM 命令文件到 MD: 时报 `550 No destination device or"
domain: "fanuc"
tags:
  - "fanuc"
  - "frvrc"
  - "v9"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4754"
summary_plain: "向 FANUC 虚拟控制器（FRVRC V9.40）FTP 上传 .CM 命令文件到 MD: 时报 `550 No destination device or path`，但 `MD:` 设备前缀、路径形态、8.3…"
trigger: "向 FANUC 虚拟控制器（FRVRC V9.40）FTP 上传 .CM 命令文件到 MD: 时报 `550 No destination device or. path`，但 `MD:` 设备前缀、路径形态、8.3 文件名全都写对了。既有课程（550 三分层）说「MD: 前缀即可离开路径层」，对非分派扩展名不成立。"
verify: "同一控制器对照实验：`STOR MD:PROBE10.TP`（假内容）→ 内容层 550；`STOR MD:PROBE10.CM/.LS/.DG`、裸名、`MD:\\`、`MD:/` 形态、8.3 名 → 全部「No destination device or path」；`STOR MD:PROBE10.HTM` → 成功；`STOR UT1:PROBE10.CM` → 成功且 `NLST…"
provenance:
  issue: "#4754"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

向 FANUC 虚拟控制器（FRVRC V9.40）FTP 上传 .CM 命令文件到 MD: 时报 `550 No destination device or path`，但 `MD:` 设备前缀、路径形态、8.3 文件名全都写对了。既有课程（550 三分层）说「MD: 前缀即可离开路径层」，对非分派扩展名不成立。

## Root Cause

MD: 的 FTP STOR 是**扩展名分派**的：.TP/.PC/.VR/.SV 各有校验器（假内容分别报 Invalid or corrupted TP file / Program version is too new / File sequence error），.HTM 等普通文件可直传；**不在分派表的扩展名（实测 .CM/.LS/.DG/无扩展名）直接报误导性的路径层 550**——看似路径错，实际是该扩展名根本不允许写 MD:。UT1:/UD1: 用户设备无分派限制，任意扩展名可写。

## Fix

按扩展名分层排错：带 MD: 前缀仍报「No destination device or path」时，先用假内容 .TP 做对照实验（若报内容层错误则路径层其实是通的），确认是扩展名不被分派后，改走 UT1:/UD1: 暂存（`STOR UT1:<名>.<ext>`）再由机器人侧取用；不要在路径形态上反复试错。

## Verification

同一控制器对照实验：`STOR MD:PROBE10.TP`（假内容）→ 内容层 550；`STOR MD:PROBE10.CM/.LS/.DG`、裸名、`MD:\`、`MD:/` 形态、8.3 名 → 全部「No destination device or path」；`STOR MD:PROBE10.HTM` → 成功；`STOR UT1:PROBE10.CM` → 成功且 `NLST UT1:` 可见。判据=同一路径形态下不同扩展名跨层报错可复现。

假内容 .TP 报内容层错 / 同形态 .CM 报路径层错 / UT1: 上传成功且 FTP list 可见，三点对照可复现

**Matched lesson (not helpful):** `problem-向-fanuc-虚拟真机器人-ftp-上传程序文件md-设备时-550`
