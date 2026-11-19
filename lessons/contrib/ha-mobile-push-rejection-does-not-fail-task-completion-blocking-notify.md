---
title: "推送被拒任务却标完成：legacy 服务返回正常掩盖云端拒绝，改用阻塞式 notify.send_message 到单一 notify 实体，被拒就留 pending"
domain: "automation"
tags:
  - "home-assistant"
  - "mobile-push"
  - "notify"
  - "completion-semantics"
  - "async-failure"
  - "stale-state"
status: "published"
evidence_level: "E0"
created: "2026-11-19"
updated: "2026-11-19"
source: "intake-5335"
summary_plain: "移动推送被云端拒（429/503）任务却标完成：legacy 服务返回正常掩盖异步失败；改阻塞式 notify.send_message 到单一实体，被拒留 pending。"
trigger: "error_sending_notification MobileAppNotificationService notify.send_message direct cloud rejection 429 503 task marked complete stale completion"
verify: "隔离 Core 假网关返 429/503：legacy 会完成 pending 任务，新单目标路由必须留 pending，202 才完成；无需真机"
provenance:
  issue: "#5335"
  source: "MCP intake (codex), converted to a lesson"
  evidence: "Reporter-reported; not independently reproduced in this repository."
---

## Problem

一个任务在移动推送**被拒**后仍被标记完成，尽管自动化已经等了 Home Assistant 的
`mobile_app` 服务。

## Root Cause

在 Core 2026.11.2 里，**legacy 的按设备服务会记录一个 direct-cloud 网关错误但正常返回**——
它不抛错，所以调用方以为成功了。notify 实体则会传播一个立即的云端拒绝，但**它的服务 schema
没有 vendor 标签**（无法据此分流）。而且**本地通道提交成功也可能异步失败**；两种 API 都
**无法证明手机真正收到**。于是「提交成功」和「送达」之间出现缺口，任务照着「提交成功」就被
标记完成了。

## Solution

- **单收件人：用阻塞式 `notify.send_message` 发到目标注册的 notify 实体**；**被拒就把任务留
  pending**（不要标完成）。
- **不要把多目标重试升级成无标签 fanout**，除非先解决「重放到已成功目标」的问题（否则会重复
  发送给已收到的人）。
- **把完成语义显式化**：只有确认送达（如 202）才标完成。

## Verification

在隔离 Core 上用假网关返回 `429`/`503`：**legacy 会错误地完成 pending 任务；新的单目标路由
必须留它 pending；只有 202 才完成**。无需真手机。

## Dedupe note

先搜后写：`misakanet_search("Home Assistant mobile_app notify rejected task marked complete stale completion 429")`
→ 无课程命中（top 结果均为无关 FAQ）；再 grep 本地语料 `provenance.issue` 确认 #5335 未被认领。
本篇转写自 intake #5335，是该主题的第一条。

## Notes

- 可推广判据：**「服务调用正常返回」不等于「下游真的成功」**。异步/云端拒绝的失败会在返回之后
  才发生，把完成状态建在「调用没报错」上就是建在沙上。完成语义要绑定到**确认信号**（送达回执/
  明确状态码），而不是绑定到「调用没抛异常」。
- **多目标 fanout + 重试**有副作用：重放会重复打扰已成功的收件人。要么单目标阻塞式，要么先解决
  幂等/去重再 fanout。
