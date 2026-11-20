---
title: "Web TP 的三个连环陷阱：单会话秒级锁、按键数字被当控制码解析、登录时钟拿到陈旧会话 id"
domain: "fanuc"
tags:
  - "web"
  - "tp"
  - "x0"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4980"
summary_plain: "自动化驱动「设备内置 Web TP」（浏览器形态的示教器）时三个连环陷阱，症状全是「命令发了、返回 0x0 成功、界面纹丝不动」：①登录接口是**单会话 + 秒级锁**——脚本连环 login 会触发「login is…"
trigger: "Problem 自动化驱动「设备内置 Web TP」（浏览器形态的示教器）时三个连环陷阱，症状全是「命令发了、返回 0x0 成功、界面纹丝不动」：①登录接口是*. 自动化驱动「设备内置 Web TP」（浏览器形态的示教器）时三个连环陷阱，症状全是「命令发了、返回 0x0 成功、界面纹丝不动」：①登录接口是**单会话…"
verify: "锁页识别：连环 login 第二次返回「login is locked」文本且不产生新 g_connect_id（修复后应等 10s 只登录一次）；数字修复：发送日志显示 0x30/0x34/0x38（而非 0x00/0x04/0x08）；认形态：发键前截屏比对两套渲染特征（经典屏=软键行文本，Web 屏=磁贴网格）。"
provenance:
  issue: "#4980"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

自动化驱动「设备内置 Web TP」（浏览器形态的示教器）时三个连环陷阱，症状全是「命令发了、返回 0x0 成功、界面纹丝不动」：①登录接口是**单会话 + 秒级锁**——脚本连环 login 会触发「login is locked」锁定页，而解析器可能从旧响应里拿到陈旧会话 id，后续按键全部发进虚空；②按键注入的**数字符号语义**：十进制解析把 '8' 解析成控制码 8（=Backspace），而面板数字键实际是 ASCII（'8'=0x38）——发键全「成功」但语义全错；③同一窗口有**两套渲染形态**（经典 KAREL 屏 vs Web 应用屏），键码语义随形态切换：同一支键在经典屏开菜单、在 Web 屏可能只是切页/无响应，Web 屏的磁贴控件对合成鼠标点击（SetCursorPos+mouse_event）无反应。

## Root Cause

Web TP 的会话层是单例的（服务端登录锁，失败后有秒级冷却）；键码通道沿用传统面板键码表但数字段与 ASCII 映射不一致；Web 屏的 UI 控件是浏览器层渲染，不消费传统合成输入或需要控件级事件。

## Fix

1. 登录：**一次登录复用会话 id**，绝不连环 login；遇「locked」响应=等 10s 冷却，且解析器必须区分「锁页」与「真登录页」（判据：锁页无 g_connect_id）；
2. 键注入：数字键一律按单字符 ASCII 发送；把「字符键/控制键」两族在工具里分开命名（text vs key），别共用一个 parse；
3. 交互前先**认形态**（截屏判断当前是经典屏还是 Web 应用屏），键码路线只对经典屏可靠；Web 屏磁贴改走 URL 直连或控件级事件通道，别用合成坐标点击硬试。

## Verification

锁页识别：连环 login 第二次返回「login is locked」文本且不产生新 g_connect_id（修复后应等 10s 只登录一次）；数字修复：发送日志显示 0x30/0x34/0x38（而非 0x00/0x04/0x08）；认形态：发键前截屏比对两套渲染特征（经典屏=软键行文本，Web 屏=磁贴网格）。
