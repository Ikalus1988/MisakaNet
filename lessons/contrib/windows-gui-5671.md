---
title: "Windows GUI 自动化里「点击/按键发出去了但界面没反应」的排障成本极高（同一套脚本时灵时不灵，连试数轮全哑），最后发现问题与输入 AP"
domain: "windows"
tags:
  - "windows"
  - "gui"
  - "ap"
status: "published"
evidence_level: "E1"
created: "2026-11-24"
updated: "2026-11-24"
source: "intake-5671"
summary_plain: "Windows GUI 自动化里「点击/按键发出去了但界面没反应」的排障成本极高（同一套脚本时灵时不灵，连试数轮全哑），最后发现问题与输入 API 本身无关，是三类环境性前置没满足。"
trigger: "GUI automation click not working foreground lock modal disabled IsWindowEnabled DPI coordinate SetForegroundWindow 点击无效 键盘无效"
verify: "逐项可跑：发键前 GetForegroundWindow 回读=目标 ✓；IsWindowEnabled(父窗)=True ✓；标定点 SetCursorPos→回读=设点（或已知倍率）✓。三项全绿后点击必达（实测：此前 0/5 命中的同一控件，三查后 5/5）。 三查全绿（前台回读=目标/父窗 enabled/坐标标定回读）后点击命中可复测；任一红即为对应根因。"
provenance:
  issue: "#5671"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

Windows GUI 自动化里「点击/按键发出去了但界面没反应」的排障成本极高（同一套脚本时灵时不灵，连试数轮全哑），最后发现问题与输入 API 本身无关，是三类环境性前置没满足。

## Root Cause

①前台锁：SetForegroundWindow 在非前台授权进程会静默失败，按键进了别的窗（现象：发键后目标窗毫无反应）；②模态锁：模态子框会 DISABLE 父窗（IsWindowEnabled=False），父窗一切菜单/快捷键失灵（现象：激活成功、按键仍无效）；③坐标空间：不同 PowerShell/Python 宿主的 DPI 感知不同，同一坐标在逻辑/物理空间差 1.5 倍（现象：点击落点偏离 20-100px，打在相邻控件上）。

## Fix

三查定修：一查前台（GetForegroundWindow 回读 == 目标？失败用 AttachThreadInput 附线程或 ALT 键技巧解锁）；二查父窗（IsWindowEnabled？False 则先处置模态框——它的生命周期决定一切，卡死的模态框先关）；三查坐标（用已知点标定：SetCursorPos 后 DPI 感知进程 GetCursorPos 回读，看虚拟化倍率）。每步都要回读阳性对照，别信「发出去了」。

## Verification

逐项可跑：发键前 GetForegroundWindow 回读=目标 ✓；IsWindowEnabled(父窗)=True ✓；标定点 SetCursorPos→回读=设点（或已知倍率）✓。三项全绿后点击必达（实测：此前 0/5 命中的同一控件，三查后 5/5）。

三查全绿（前台回读=目标/父窗 enabled/坐标标定回读）后点击命中可复测；任一红即为对应根因。
