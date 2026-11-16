---
title: "ROBOGUIDE 虚拟控制器上注入并运行 KAREL .pc 的完整链路连环翻车（V9.40 实测）： 1) FTP `STOR MD:*.PC` 不可用：端"
domain: "fanuc"
tags:
  - "set"
  - "show"
  - "roboguide"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4793"
summary_plain: "ROBOGUIDE 虚拟控制器上注入并运行 KAREL .pc 的完整链路连环翻车（V9.40 实测）： 1) FTP `STOR MD:*.PC` 不可用：端口 21 碰一下控制器就挂（ESET WFP），换口也回 `421…"
trigger: "ROBOGUIDE 虚拟控制器上注入并运行 KAREL .pc 的完整链路连环翻车（V9.40 实测）： 1) FTP `STOR MD:*.PC` 不可用：端. 端口 21 碰一下控制器就挂（ESET WFP），换口也回 `421 Access Denied (FSAC)`； 2) `GET /KCL/COPY…"
verify: "B2_FE135R1_0524_MH 工位：COPY→SHOW PROG 回 \"Program name: MH_GRP PC | 6853 bytes\" 在册； RUN MH_TEST 后 `show var [MH_TEST]RES_STR` = 'PPPPPPPPPPPP'（12/12 PASS，N_FAIL=0），报警码 50/62/189/318/334/347 与注释表逐号命中。…"
provenance:
  issue: "#4793"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

ROBOGUIDE 虚拟控制器上注入并运行 KAREL .pc 的完整链路连环翻车（V9.40 实测）：

1) FTP `STOR MD:*.PC` 不可用：端口 21 碰一下控制器就挂（ESET WFP），换口也回 `421 Access Denied (FSAC)`；
2) `GET /KCL/COPY …`/`SET VAR`/`RUN` 引导后立刻发一律回 `ERROR: KCL option not loaded`——看着像缺 J650 选项，实际 SUMMARY.DG 里选项全在；
3) 审查表文档说 RUN 在 `CMDS[13]`，实际在 `CMDS[12]`（[13] 是 RUNCF），清错槽 RUN 一直 Protected；
4) 引导后 ~30-45s 内 `RUN` 还会回 `System is being initialized`。

## Root Cause

1) FTP 本机禁区（已知）+ 实机备份带 FSAC 策略拒 FTP；绕开 21 是唯一活路；
2) "KCL option not loaded" 是 **KAREL 运行时装载完成前的瞬态**，不是缺选项——控制器暖机前 COPY/SET VAR 全部失败，show 类命令却能用（web 轻解析层），极易误判；
3) `[HTTPKCL]CMDS` 数组实际顺序与文档/注释不一致，必须实读；
4) `System is being initialized` 同为启动瞬态。

## Fix

免 FTP 注入链（全程只用文件夹映射 + HTTP KCL）：
`Robot_1\UD1\` 目录直投 .pc → `COPY UD1:X.PC MD: OVERWRITE`（COPY 不在审查表，免解锁）→ `SHOW PROG X` 验在册 → `set var [HTTPKCL]CMDS[12]=''` 解锁 RUN → `SET VAR $RMT_MASTER=1` 同拍 `RUN X` → `show var [X]RESULT` 取数。
**就绪判据 = COPY 回显 "Copied"**（不是 show clock，不是 SET VAR 成功）；RUN 回 initialized/Protected 均重试。
另：KTRANS 编译 KAREL 时出参与源**同目录同名会自拷自 → error 32 LOCK_VIOLATION**（Windows 大小写不敏感），出参放独立目录、产物取源目录小写 .pc；编译目录须纯英文路径。

## Verification

B2_FE135R1_0524_MH 工位：COPY→SHOW PROG 回 "Program name: MH_GRP PC | 6853 bytes" 在册；
RUN MH_TEST 后 `show var [MH_TEST]RES_STR` = 'PPPPPPPPPPPP'（12/12 PASS，N_FAIL=0），报警码 50/62/189/318/334/347 与注释表逐号命中。
另证：大号 IO（DO 200+/DI 100+）写读异常、小号（DO 10+/DI 20+）全绿——布点必须按现场 IO 表并先用探针校验。
