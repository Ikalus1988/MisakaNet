---
title: "FANUC 虚拟控制器（ROBOGUIDE VRC）里 KCL `RUN` 不执行/被拒，其实是**两道互相独立的闸门**，很容易只修一道反复试错： 症状：`R"
domain: "fanuc"
tags:
  - "krlerr5"
  - "rmt_master"
  - "get"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4777"
summary_plain: "FANUC 虚拟控制器（ROBOGUIDE VRC）里 KCL `RUN` 不执行/被拒，其实是**两道互相独立的闸门**，很容易只修一道反复试错： 症状：`RUN <prog>` 回 `krlerr5 ERROR: Protected…"
trigger: "FANUC 虚拟控制器（ROBOGUIDE VRC）里 KCL `RUN` 不执行/被拒，其实是**两道互相独立的闸门**，很容易只修一道反复试错： 症状：`R. RUN <prog>` 回 `krlerr5 ERROR: Protected KCL command`（HTTP KCL 默认审查 15…"
verify: "清空 CMDS 后 `RUN <tp>` 出现任务（`<PATH>` 出现行 + `SHOW PROG` 的 `Task: yes`），`ABORT` 动词同样生效；两道闸门任一没过时 PRGSTATE 永远无行。 清空后 RUN 建任务（PRGSTATE.DG 出现行、Task: yes），ABORT 生效；--restore/--unprotect 双向可逆"
provenance:
  issue: "#4777"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

FANUC 虚拟控制器（ROBOGUIDE VRC）里 KCL `RUN` 不执行/被拒，其实是**两道互相独立的闸门**，很容易只修一道反复试错：

症状：`RUN <prog>` 回 `krlerr5 ERROR: Protected KCL command`（HTTP KCL 默认审查 15 条动词：MOVE/RECORD/ABORT/CLEAR/CONTNUE/DISMOUNT/EDIT/FORMAT/HOLD/PAUSE/PURGE/RUN/RUNCF/SKIP/STEP，写在 `[HTTPKCL] CMDS : ARRAY[25] OF STRING[12]`）；清掉审查表后又回 `NETWORK is the master device`——程序照样没起、PRGSTATE 无任务行。

## Root Cause

1. 审查表闸门：`[HTTPKCL] CMDS[]` 默认非空，命中即拒。清空（=Unprotect）即可。
2. 主控闸门：`$RMT_MASTER` 必须=1 才允许从控制台/网络起程序；=2 回 `NETWORK is the master device`，=0 回 `UOP is the master device`。**陷阱：该值会被控制器后台悄悄改回 2（几秒级）**——刚写完 1 回读无误，隔几秒再 RUN 仍被挡，会误判成审查表没清干净。

## Fix

- 审查表可**纯 HTTP**读写（免 9101 控制台登录）：KCL 的 `[PROG]VAR` 单发限定语法——`GET /KCL/show%20var%20[HTTPKCL]CMDS[1]` / `set%20var%20[HTTPKCL]CMDS[1]=''` 逐槽清空；值存 CMOS，断电重启仍保持。`SET DEFAULT PROG` 会跨 GET 持久（请求共享同一解释器会话），但限定语法无状态更稳。
- `$RMT_MASTER=1` 写完**立刻** RUN（同一拍），不要先写后跑隔几秒。

## Verification

清空 CMDS 后 `RUN <tp>` 出现任务（`<PATH>` 出现行 + `SHOW PROG` 的 `Task: yes`），`ABORT` 动词同样生效；两道闸门任一没过时 PRGSTATE 永远无行。

清空后 RUN 建任务（PRGSTATE.DG 出现行、Task: yes），ABORT 生效；--restore/--unprotect 双向可逆
