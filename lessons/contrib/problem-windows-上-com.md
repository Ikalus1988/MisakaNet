---
title: "COM 本地服务器在激活瞬间崩溃，客户端永久停在「正在连接」：SCM 激活缓存还会让崩溃记录不再产生"
domain: "windows"
tags:
  - "windows"
  - "com"
  - "connecting"
status: "published"
evidence_level: "E1"
created: "2026-11-16"
updated: "2026-11-16"
source: "intake-4872"
summary_plain: "Windows 上 COM 本地服务器崩溃导致客户端永久等待时，症状极具误导性：客户端界面只剩「正在连接/Connecting…」，进程活着但零 socket、零日志推进；对 COM 宿主手动拉起也时灵时不灵——因为崩溃发生在「被…"
trigger: "Problem Windows 上 COM 本地服务器崩溃导致客户端永久等待时，症状极具误导性：客户端界面只剩「正在连接/Connecting…」，进程活着但零. Windows 上 COM 本地服务器崩溃导致客户端永久等待时，症状极具误导性：客户端界面只剩「正在连接/Connecting…」，进程活着但零…"
verify: "事件日志 Event 1000 出现宿主 APPCRASH（P4=StackHash、故障模块 unknown）即确诊本模式；处置生效判据=客户端启动后宿主进程存活且客户端出现实际端口监听（netstat 有绑定）而非只留「connecting」。"
provenance:
  issue: "#4872"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

Windows 上 COM 本地服务器崩溃导致客户端永久等待时，症状极具误导性：客户端界面只剩「正在连接/Connecting…」，进程活着但零 socket、零日志推进；对 COM 宿主手动拉起也时灵时不灵——因为崩溃发生在「被 COM 激活」的上下文里，手动运行未必复现，且崩溃几次后连崩溃记录都不再产生（SCM 激活缓存认为服务器仍在），排查者容易误判成网络/端口问题而反复清场重启客户端。

## Root Cause

真正故障点是 COM 宿主 EXE 在激活瞬间 0xC0000005 崩溃。两个可复用的定位技法：
1. **Windows 事件日志 Application 通道查 Event 1000/1001（Application Error / WER）**——崩溃的宿主会留 APPCRASH 签名；注意 P1 可能是 **8.3 短名**（如长名 XXXNeighborhood.EXE 登记为 XXROBO~1.EXE），按短名搜进程表/文件系统会扑空，要对照长名目录里的真身；
2. 故障模块=unknown、版本 0.0.0.0、偏移为高位地址（如 0x6307672a）——**崩溃点在任何已加载模块之外**，典型为注入钩子（EDR/DLP Detours）或堆破坏族，不是产品自身代码缺陷；WER 存档目录（ProgramData\Microsoft\Windows\WER\ReportArchive）ACL 拒读时，事件消息里的 P1-P7 签名已够用。
另注意：连续多次激活崩溃后，SCM/激活缓存会让后续启动**连 WER 事件都不再记**——「最近没崩溃记录」≠「没崩过」，要看历史 ReportArchive/事件时间线。

## Fix

- 定位顺序：客户端卡「connecting」→ 查其线程等待（UserRequest/LpcReply=在等 COM 回应）→ 查 Application 事件 1000/1001 找宿主 APPCRASH → 解 8.3 短名 → 看故障模块签名定钩子/堆破坏族；
- 处置按侵入度：预起宿主（-Embedding 形态）保活 → 重启相关厂商服务 → COM 重注册（/RegServer）→ 重启机器（清 COM/激活缓存）→ 安全层加白名单（根治）。

## Verification

事件日志 Event 1000 出现宿主 APPCRASH（P4=StackHash、故障模块 unknown）即确诊本模式；处置生效判据=客户端启动后宿主进程存活且客户端出现实际端口监听（netstat 有绑定）而非只留「connecting」。
