---
title: "VB6 自绘树控件只认真实输入链路：合成消息不触发选中，老化实例还会静默降级"
domain: "windows"
tags:
  - "problem"
  - "windows"
  - "vb6"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4600"
summary_plain: "Windows 上自动化 VB6 自绘树控件（如 ThunderRT6/TreeView20WndClass 类）时，合成输入全部失效：SendMessage WM_LBUTTONDOWN/UP…"
trigger: "Problem Windows 上自动化 VB6 自绘树控件（如 ThunderRT6/TreeView20WndClass 类）时，合成输入全部失效：Send. Windows 上自动化 VB6 自绘树控件（如 ThunderRT6/TreeView20WndClass…"
verify: "标定实验（点展开框看树是否响应）可 30 秒内区分「坐标错」vs「通道失聪」；同一控件同一坐标下：老实例真实点击无反应（判定恒为红字），杀掉重启新实例后同一真实点击立即注册（校验弹出真实解析进度框并给出绿字通过判定），可复现。 新老实例对照：老实例点击失聪、新实例同坐标即注册，30 秒标定实验可判别"
provenance:
  issue: "#4600"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

Windows 上自动化 VB6 自绘树控件（如 ThunderRT6/TreeView20WndClass 类）时，合成输入全部失效：SendMessage WM_LBUTTONDOWN/UP 只能触发展开切换、不注册节点选中（业务路径变量不写）；SendKeys 字母做增量搜索只动焦点；UIA 查 TreeItem/ListItem 均为 0（自绘控件无可访问性暴露）；补全 NCHITTEST→SETCURSOR→MOUSEMOVE→BUTTONDOWN/UP 消息握手仍无效。更隐蔽的坑：长时间存活（数天）的 VB6 实例会「内伤」——连真实鼠标点击也不再响应，表现为验证判定永远停在初始红字（选中未注册的假阴性）。

## Root Cause

VB6 自绘控件的 NodeClick/选中逻辑可能依赖真实输入子系统的完整链路（含焦点/捕获/消息时序），合成消息不满足；且 VB6 老化实例的消息循环/输入处理会静默降级。假阴性（校验文字不刷新）极易被误判为「数据无效」，实际是点击从未注册。

## Fix

标定点击自检 + 真实点击 + TOPMOST 防遮挡 + 判定不刷新先怀疑选中未注册/实例老化

## Verification

标定实验（点展开框看树是否响应）可 30 秒内区分「坐标错」vs「通道失聪」；同一控件同一坐标下：老实例真实点击无反应（判定恒为红字），杀掉重启新实例后同一真实点击立即注册（校验弹出真实解析进度框并给出绿字通过判定），可复现。

新老实例对照：老实例点击失聪、新实例同坐标即注册，30 秒标定实验可判别
