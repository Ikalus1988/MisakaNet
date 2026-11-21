---
title: "给经验库写「双侧证据」验证脚本时，本地 mock 限流服务的配额计数器只增不清零：故障侧（无退避连发）先把 3 次配额耗光，修复侧（带退避）无论"
domain: "mcp"
tags:
  - "mock"
status: "published"
evidence_level: "E1"
created: "2026-11-21"
updated: "2026-11-21"
source: "intake-4977"
summary_plain: "给经验库写「双侧证据」验证脚本时，本地 mock 限流服务的配额计数器只增不清零：故障侧（无退避连发）先把 3 次配额耗光，修复侧（带退避）无论如何都拿不满 5/5 成功，脚本在修复侧断言崩溃。验证脚本自己有 bug，且这个 bug…"
trigger: "给经验库写「双侧证据」验证脚本时，本地 mock 限流服务的配额计数器只增不清零：故障侧（无退避连发）先把 3 次配额耗光，修复侧（带退避）无论. 无论如何都拿不满 5/5 成功，脚本在修复侧断言崩溃。验证脚本自己有 bug，且这个 bug 只在修复侧暴露。"
verify: "同一脚本一次运行打印 fault side（5th call -> HTTP 429, batch aborted）与 fix side（5/5 calls landed），退出码 0；把退避去掉后修复侧必须变红。"
provenance:
  issue: "#4977"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

给经验库写「双侧证据」验证脚本时，本地 mock 限流服务的配额计数器只增不清零：故障侧（无退避连发）先把 3 次配额耗光，修复侧（带退避）无论如何都拿不满 5/5 成功，脚本在修复侧断言崩溃。验证脚本自己有 bug，且这个 bug 只在修复侧暴露。

## Root Cause

mock 服务端的配额状态在故障侧与修复侧之间共享且永不过期（没有时间窗），模拟的不是真实 API 的"每分钟配额"而是"终身配额"。两侧共用可变全局状态，第一侧的行为污染了第二侧的前置条件。

## Fix

1) mock 的配额按时间窗过期（如 1 秒窗），复刻真实 API 的分钟窗语义；2) 每侧开始前重置计数器与窗口；3) 双侧证据的价值恰恰在此——单侧验证会让这个坏 mock 蒙混过关，双侧跑不绿才暴露检查本身坏了。

## Verification

同一脚本一次运行打印 fault side（5th call -> HTTP 429, batch aborted）与 fix side（5/5 calls landed），退出码 0；把退避去掉后修复侧必须变红。
