---
title: "GUI 进程 spawn 控制台子进程：每次调用闪一个黑窗，诊断输出刷屏"
domain: "windows"
tags:
  - "problem"
  - "windows"
  - "gui"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-3972"
summary_plain: "Windows GUI 桌面应用在功能里调用命令行小工具（私有二进制转换器），每次调用都**闪出一个控制台窗口**并打印工具的无害唠叨（如 'Unable to find xxx.ini'）。导入百台级备份时每个文件调一次 →…"
trigger: "Problem Windows GUI 桌面应用在功能里调用命令行小工具（私有二进制转换器），每次调用都**闪出一个控制台窗口**并打印工具的无害唠叨（如 'U. Windows GUI 桌面应用在功能里调用命令行小工具（私有二进制转换器），每次调用都**闪出一个控制台窗口**并打印工具的无害唠叨（如…"
verify: "cargo test 全绿；导入百台级备份真机实测功能正常（TPP/负载照出）；conhost 计数采样无尖峰（旁证）；用户目测弹窗绝迹（终判据）。"
provenance:
  issue: "#3972"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

Windows GUI 桌面应用在功能里调用命令行小工具（私有二进制转换器），每次调用都**闪出一个控制台窗口**并打印工具的无害唠叨（如 'Unable to find xxx.ini'）。导入百台级备份时每个文件调一次 → 窗口刷屏，用户以为程序中毒。此前该功能因别的 bug 一直没跑起来，修复后弹窗问题才暴露。

## Root Cause

Windows 上 GUI 子系统（非控制台）的进程 spawn 命令行子进程时，默认会为子进程**分配可见控制台**；工具又把诊断信息写 stderr，窗口一闪而过、逐次弹出。调用方用了 `.status()` 继承句柄，stderr 噪音直接怼到那个可见窗口上。

## Fix

1. 子进程加 `CREATE_NO_WINDOW`（Windows 进程创建标志 0x08000000，Rust 用 `std::os::windows::process::CommandExt::creation_flags`，cfg(windows) 门控）；
2. 子进程 stdout/stderr 显式 `Stdio::null()`——这类 CLI 的唠叨是已知无害路径（成败以输出文件为准），既不弹窗也不刷日志；
3. 横扫进程内所有 spawn 点，区分「本该有窗」（如 explorer 打开文件夹）与「干活型工具」（一律无窗）。
判据：批量转换几百次期间可见窗口零弹出；工具输出文件照常产出（功能判据不变）。

## Verification

cargo test 全绿；导入百台级备份真机实测功能正常（TPP/负载照出）；conhost 计数采样无尖峰（旁证）；用户目测弹窗绝迹（终判据）。
