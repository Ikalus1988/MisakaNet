---
title: "ROBOGUIDE（FANUC 离线仿真）GUI 菜单「示教→创建TP程序」生成并加载新程序时报错：弹窗「错误 加载 program XXX — No dest"
domain: "fanuc"
tags:
  - "optn-007"
  - "no"
  - "or"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-5036"
summary_plain: "ROBOGUIDE（FANUC 离线仿真）GUI 菜单「示教→创建TP程序」生成并加载新程序时报错：弹窗「错误 加载 program XXX — No destination device or path」，状态栏 `OPTN-007…"
trigger: "ROBOGUIDE（FANUC 离线仿真）GUI 菜单「示教→创建TP程序」生成并加载新程序时报错：弹窗「错误 加载 program XXX — No dest. destination device or path」，状态栏 `OPTN-007 Unauthorized: 'R507 Ascii…"
verify: "TP 路线全链实测：新建（SHOW PROGS +1）→ 编辑插入指令（Lines 0→1）→ 复制行（EDCMD Copy/Cut/Paste，Lines 1→2）→ 运行（SHIFT+FWD，副作用寄存器回读 0→1）。四步判据全部成立。 SHOW PROGS +1 / Lines 0→1→2 / 寄存器副作用 0→1 四步判据 **Matched lesson (not…"
provenance:
  issue: "#5036"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

ROBOGUIDE（FANUC 离线仿真）GUI 菜单「示教→创建TP程序」生成并加载新程序时报错：弹窗「错误 加载 program XXX — No destination device or path」，状态栏 `OPTN-007 Unauthorized: 'R507 Ascii Upload'`，程序不入册。控制器上该选项在订单文件里「有行」但未授权（软选项装了没功能密钥）。

## Root Cause

GUI 的程序生成走内部 SimPRO 管线（fblnGenerateAndLoadNewProgram）：PC 侧生成 .TP 后经 **ASCII Upload（R507 选项）** 传入控制器——R507 未授权即整链断（OPTN-007）。注意与 FTP 上传的 550 No destination device or path（路径层问题）区分：同文案不同通道不同根因。失败后 GUI 还会留「鬼影选择」（msubSelectTPProgram 对幽灵程序反复报 Program does not exist），任何程序菜单动作都触发循环报错。

## Fix

改走 **TP 屏（示教器）本侧创建**：SELECT 屏 → CREATE 软键 → 输名 → ENTER → EDIT——这是控制器内部创建，**不经过 ASCII Upload，不吃 R507**。鬼影选择清法=重启 GUI（或选一个真实程序顶掉）。

## Verification

TP 路线全链实测：新建（SHOW PROGS +1）→ 编辑插入指令（Lines 0→1）→ 复制行（EDCMD Copy/Cut/Paste，Lines 1→2）→ 运行（SHIFT+FWD，副作用寄存器回读 0→1）。四步判据全部成立。

SHOW PROGS +1 / Lines 0→1→2 / 寄存器副作用 0→1 四步判据

**Matched lesson (not helpful):** `problem-向-fanuc-虚拟真机器人-ftp-上传程序文件md-设备时-550`
