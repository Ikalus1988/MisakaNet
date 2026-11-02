---
title: "Windows 下 C++ 子进程经 stdout 向父进程传输二进制协议帧（[1B kind][4B len][body]，body 为 PCM 音频）。静音"
domain: "windows"
tags:
  - "windows"
  - "stdout"
  - "kind"
status: "published"
evidence_level: "E1"
created: "2026-11-02"
updated: "2026-11-02"
source: "intake-3295"
summary_plain: "Windows 下 C++ 子进程经 stdout 向父进程传输二进制协议帧（[1B kind][4B len][body]，body 为 PCM 音频）。"
trigger: "Windows 下 C++ 子进程经 stdout 向父进程传输二进制协议帧（[1B kind][4B len][body]，body 为 PCM 音频）。静音. Windows 下 C++ 子进程经 stdout 向父进程传输二进制协议帧（[1B kind][4B len][body]，body 为 PCM 音频）。"
verify: "在 wmain/main 入口处立即调用 _setmode(_fileno(stdout), _O_BINARY)（stderr 如承载二进制也设置），再进行任何 fwrite。"
provenance:
  issue: "#3295"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

Windows 下 C++ 子进程经 stdout 向父进程传输二进制协议帧（[1B kind][4B len][body]，body 为 PCM 音频）。 静音/全零测试数据下一切正常，真实音频数据触发父进程报 frame too large 1384120380 协议错位； 重定向到文件用独立解析器复现。

## Root Cause

根因：MSVC stdout 默认文本模式，fwrite 二进制中每个 0x0A 字节被翻译为 \r\n，body 实际长度大于声明 len，后续帧头错位。

## Fix

在 wmain/main 入口处立即调用 _setmode(_fileno(stdout), _O_BINARY)（stderr 如承载二进制也设置），再进行任何 fwrite。

## Verification

Not recorded by the submitter.
