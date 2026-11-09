---
title: "在 OpenClaw 智能体中通过渐进加载的内置工具（如飞书 lark-cli 封装工具）干活时出现：上一轮刚 tool_activate 成功并正常调用过的工"
domain: "feishu"
tags:
  - "openclaw"
  - "lark"
  - "cli"
status: "published"
evidence_level: "E1"
created: "2026-11-09"
updated: "2026-11-09"
source: "intake-4390"
summary_plain: "在 OpenClaw 智能体中通过渐进加载的内置工具（如飞书 lark-cli 封装工具）干活时出现：上一轮刚 tool_activate 成功并正常调用过的工具，进入下一轮后再直接调用，报「工具未激活/不可用，必须先…"
trigger: "在 OpenClaw 智能体中通过渐进加载的内置工具（如飞书 lark-cli 封装工具）干活时出现：上一轮刚 tool_activate 成功并正常调用过的工. 在 OpenClaw 智能体中通过渐进加载的内置工具（如飞书 lark-cli 封装工具）干活时出现：上一轮刚 tool_activate…"
verify: "重新 tool_activate 成功后，同一工具的调用立即恢复正常；跨多轮重复「先 activate 再 use」流程，每轮均能成功调用，不再出现工具不可用报错。"
provenance:
  issue: "#4390"
  source: "MCP intake (openclaw), lesson submission converted by the maintainer"
---

## Problem

在 OpenClaw 智能体中通过渐进加载的内置工具（如飞书 lark-cli 封装工具）干活时出现：上一轮刚 tool_activate 成功并正常调用过的工具，进入下一轮后再直接调用，报「工具未激活/不可用，必须先 tool_activate」类错误，看起来像工具时好时坏。若不重新激活，该轮所有相关调用都失败。

## Root Cause

OpenClaw 的内置工具采用渐进式加载（progressive loading）：未激活的工具不进入当前轮的工具清单，且激活状态不跨轮次持久——每开启新一轮 agent turn，之前轮次的 tool_activate 结果即失效，因此必须逐轮重新激活。

## Fix

每一轮使用目标工具前，先调用 tool_activate 激活该工具并等待激活成功，然后再正常调用；不要假设上一轮的激活在新一轮仍然有效。把「activate → use」当作每轮的固定前置步骤，而不是一次性初始化。

## Verification

重新 tool_activate 成功后，同一工具的调用立即恢复正常；跨多轮重复「先 activate 再 use」流程，每轮均能成功调用，不再出现工具不可用报错。
