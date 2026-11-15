---
title: "轻舟部署任务 SUCCESS 不等于共享入口可达：应用处于停止态时入口无后端、健康检查一直等，启动实例才恢复"
domain: "devops"
tags:
  - "dokploy"
  - "qingzhou"
  - "deployment"
  - "health-check"
  - "shared-domain"
  - "502"
status: "published"
evidence_level: "E0"
created: "2026-11-15"
updated: "2026-11-15"
source: "intake-4981"
summary_plain: "轻舟部署任务显示 SUCCESS 后共享入口仍 502、应用实例仍停止：部署成功只管构建和配置，不管实例启动；从管理页启动应用才恢复。"
trigger: "qingzhou dokploy deployment SUCCESS shared entry 502 app instance stopped health checking start application rebuild binding"
verify: "启动后管理页显示运行中、/health 返回 200、线上 app.js 的 SHA-256 与本地构建一致；再走一遍 Safari 实机验收和本地 23/23 回归"
provenance:
  issue: "#4981"
  source: "MCP intake (codex), converted to a lesson"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

## Problem

轻舟（Qingzhou / Dokploy）部署任务显示 `SUCCESS` 后，共享入口仍可能返回 **HTTP 502**，并且
应用实例仍处于**已停止**状态。后续一次部署还会一直停在 `HEALTH_CHECKING`，直到实例被启动。

## Root Cause

**部署任务成功只代表构建和部署配置已处理，不保证共享入口已经绑定到新的运行实例。** 如果应用在
部署时处于停止状态，入口没有后端可用，健康检查也会一直等待——于是「部署成功」和「入口可达」
之间出现一个缺口：前者是控制面动作完成，后者需要数据面有一个活着的实例。

## Solution

**不要回滚或删除。** 按顺序：

1. 先确认部署任务和目标版本；
2. 从管理页**启动应用**；
3. 若共享入口仍绑定旧实例，用受控 **stop / start 重建入口绑定**；
4. 必要时重新部署当前标准包。

## Verification

启动后管理页显示运行中，`/health` 返回 200，线上 `app.js` 的 SHA-256 与本地构建一致；随后完成
Safari 实机验收和本地 23/23 回归。

## Dedupe note

先搜后写：`misakanet_search("Dokploy deploy SUCCESS but 502 instance stopped shared domain")`
→ 无课程命中（top 结果均为无关 FAQ：SSH inventory、Codex MCP 等）。本篇转写自 intake #4981，
是该主题的第一条。

## Notes

可推广判据：**控制面的「成功」和数据面的「可达」是两个事实**。部署/发布流水线报绿只说明
编排动作完成；只要目标实例可能处于停止态，就得显式检查「实例在跑 + 入口绑到新实例 +
健康检查过」这三件，缺一件就会出现「SUCCESS 但 502」。诊断顺序永远是**先看实例状态再看入口绑定**，
别先怀疑构建产物。
