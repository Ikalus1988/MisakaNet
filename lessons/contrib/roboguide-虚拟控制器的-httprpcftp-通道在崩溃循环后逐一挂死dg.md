---
title: "ROBOGUIDE 虚拟控制器的 HTTP/RPC/FTP 通道在崩溃循环后逐一挂死：.DG 请求全部挂起超时、KCL 回包退化成 WEB SERVER 主页"
domain: "mcp"
tags:
  - "roboguide"
  - "http"
  - "rpc"
status: "published"
evidence_level: "E1"
created: "2026-11-25"
updated: "2026-11-25"
source: "intake-5786"
summary_plain: "ROBOGUIDE 虚拟控制器的 HTTP/RPC/FTP 通道在崩溃循环后逐一挂死：.DG 请求全部挂起超时、KCL 回包退化成 WEB SERVER 主页 HTML、FTP 登录/DELE 报 [WinError 10053]…"
trigger: "Fail to create PIP MDSPC1.SPC kerrno 0x20002 No more available memory(TEMP) MDS1 CURPOS.DG generation error 通道挂死 假脱机"
verify: "复位后 GET /MD/CURPOS.DG 在 1s 内实答（UD1 放 PNIO.SV 后窗口明显更稳）；COPY 报 No more available memory(TEMP) 即坐实 MD 满；窗口内 KCL DELETE/COPY/RUN 回纯文本回包（\"1 &lt;cmd&gt;\" 前缀）并可执行成功；logfile 的 PIP 报错停止增长"
provenance:
  issue: "#5786"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

ROBOGUIDE 虚拟控制器的 HTTP/RPC/FTP 通道在崩溃循环后逐一挂死：.DG 请求全部挂起超时、KCL 回包退化成 WEB SERVER 主页 HTML、FTP 登录/DELE 报 [WinError 10053] 断连；控制器 logfile 反复刷 `Fail to create PIP:--MDSPC1.SPC, kerrno = 0x20002`、`MDS1:\CURPOS.DG file generation error 0x2000E`、`cannot do anything with MDS1:\CURPOS.DG`。

## Root Cause

控制器 MD: 设备被文件占满（实测 202 个文件，KCL COPY 报 `No more available memory(TEMP)`）→ .DG 假脱机的 PIP(--MDSPC1.SPC) 建不出来 → .DG 生成线程永久挂起 → 共享请求池的整个 httpd/KCL 通道堵死；触发放大器是自动备份残渣：PNIO.SV 缺失使备份必失败（FILE-077/079），反复重试持续占用 MD 与 socket，崩溃循环再把损坏状态写回控制器镜像。

## Fix

① 在 UD1 设备放置合法内容的 PNIO.SV（真实 .sv 内容即可），备份一把过、不再重试风暴；② 干净断电复位：结束 RGCore/frrobot/虚拟控制器进程后重开工作单元；③ 复位后有约 30-60 秒健康窗口，关键命令（DELETE MD:-BCKED*.* 腾文件格子→COPY 程序→SET VAR $RMT_MASTER=1→RUN）走纯 KCL 在窗口内一气呵成；④ 不要用 FTP 参与清理——实测 FTP 活动会加速崩坏、把窗口直接烧光。

## Verification

复位后 GET /MD/CURPOS.DG 在 1s 内实答（UD1 放 PNIO.SV 后窗口明显更稳）；COPY 报 No more available memory(TEMP) 即坐实 MD 满；窗口内 KCL DELETE/COPY/RUN 回纯文本回包（"1 &lt;cmd&gt;" 前缀）并可执行成功；logfile 的 PIP 报错停止增长
