---
title: "用 CronCreate 建了每 15 分钟一轮的跟踪任务后会话闲置十几小时，恢复时一次性收到 48 条相同的排队触发消息，每条都会再执行一遍任"
domain: "mcp"
tags:
  - "croncreate"
status: "published"
evidence_level: "E1"
created: "2026-11-21"
updated: "2026-11-21"
source: "intake-4976"
summary_plain: "用 CronCreate 建了每 15 分钟一轮的跟踪任务后会话闲置十几小时，恢复时一次性收到 48 条相同的排队触发消息，每条都会再执行一遍任务。反复触发的循环任务在闲置会话里会积压排队，恢复后洪水式送达。"
trigger: "用 CronCreate 建了每 15 分钟一轮的跟踪任务后会话闲置十几小时，恢复时一次性收到 48 条相同的排队触发消息，每条都会再执行一遍任. 每条都会再执行一遍任务。反复触发的循环任务在闲置会话里会积压排队，恢复后洪水式送达。"
verify: "CronList 确认 job 已删除；后续消息里不再出现同质重复触发；批量消息按一轮汇报后无新增排队。"
provenance:
  issue: "#4976"
  source: "MCP intake (claude-code), lesson submission converted by the maintainer"
---

## Problem

用 CronCreate 建了每 15 分钟一轮的跟踪任务后会话闲置十几小时，恢复时一次性收到 48 条相同的排队触发消息，每条都会再执行一遍任务。反复触发的循环任务在闲置会话里会积压排队，恢复后洪水式送达。

## Root Cause

定时任务只在 REPL 空闲时开火；间隔短（15 分钟）的 recurring job 遇上长时间无人值守的会话，每一轮都排进队列而不是丢弃，恢复后批量送达，造成同质触发风暴。

## Fix

1) 收到批量重复触发时按 1 轮合并处理，不要逐条响应；2) 立即 CronDelete 掉 recurring job 止损；3) 有限轮次的跟踪改用一次性定时（recurring:false）或直接在任务里内联完成，不依赖短间隔 recurring cron。

## Verification

CronList 确认 job 已删除；后续消息里不再出现同质重复触发；批量消息按一轮汇报后无新增排队。
